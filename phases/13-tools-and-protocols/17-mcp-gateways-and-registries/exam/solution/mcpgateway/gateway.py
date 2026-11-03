"""One stateless MCP endpoint in front of several backend servers.

Every request is authenticated, validated, routed, authorized and rate limited on its
own, then sent to its backend as a fresh, self-contained request. Nothing here is a
protocol session: the only state is application data (rate windows, task routes and
the audit trail).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol

from .backends import Backend
from .limits import LimitKey, RateLimiter
from .policy import CallContext, Decision
from .relay import Hop, TaskNotFound, TaskRoutes, relay
from .wire import (
    CLIENT_CAPABILITIES_META,
    GATEWAY_INFO,
    TASK_METHODS,
    ProtocolError,
    check_response,
    error_response,
    gateway_result,
    make_request,
    mediated,
    request_meta,
    routing_headers,
    state_digest,
    success,
    trace_id_of,
    validate_wire,
)


@dataclass(frozen=True)
class Principal:
    """An authenticated caller: subject `id` at `issuer`, with a token for `resource`."""

    id: str
    issuer: str
    resource: str
    tenant: str
    roles: frozenset[str] = frozenset()

    @property
    def key(self) -> tuple[str, str]:
        return (self.issuer, self.id)


@dataclass(frozen=True)
class Route:
    """A public tool: the backend that serves it, the tool's name there, and its policy inputs.

    `operation` is "read" or "write"; it is also the call's cost class for rate limits.
    """

    backend: str
    tool: str
    operation: str = "read"
    classification: str = "internal"
    tenant_arg: str | None = None
    admitted: bool = True
    pinned: bool = True


@dataclass(frozen=True)
class Admitted:
    """A validated request from an authenticated caller, as the gateway handles it."""

    principal: Principal
    method: str
    request_id: Any
    params: dict[str, Any]
    headers: dict[str, str]
    capabilities: dict[str, Any]  # what the gateway declares to the backend for this request
    started: float
    public: str | None = None  # tools/call: the public tool name
    route: Route | None = None  # tools/call: its route


class Policy(Protocol):
    def decide(self, ctx: CallContext) -> Decision: ...


class Audit(Protocol):
    def record(self, event: dict[str, Any]) -> dict[str, Any]: ...


class Refusal(Exception):
    """A request answered by the gateway itself: an HTTP status and a JSON-RPC error."""

    def __init__(self, status: int, error: ProtocolError) -> None:
        super().__init__(error.message)
        self.status = status
        self.error = error


def http_status(error: ProtocolError) -> int:
    if error.code == -32601:
        return 404
    if error.code == -32603:
        return 502
    return 400


class Gateway:
    def __init__(
        self,
        *,
        principals: dict[str, Principal],
        routes: dict[str, Route],
        backends: dict[str, Backend],
        credentials: dict[tuple[str, str], str],
        policy: Policy,
        limiter: RateLimiter,
        audit: Audit,
        clock: Callable[[], float],
        mediates: dict[str, Any] | None = None,
        tasks: TaskRoutes | None = None,
    ) -> None:
        """`principals` maps a caller's bearer token to who they are. `credentials` maps a
        backend's (issuer, resource) to the gateway's own token there. `mediates` holds
        the client capabilities the gateway can carry end to end."""
        self.principals = principals
        self.routes = routes
        self.backends = backends
        self.credentials = credentials
        self.policy = policy
        self.limiter = limiter
        self.audit = audit
        self.clock = clock
        self.mediates = dict(mediates or {})
        self.tasks = tasks if tasks is not None else TaskRoutes()
        self._sent = 0

    def handle(self, body: dict[str, Any], headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
        """Answer one JSON-RPC request, given its HTTP headers, with (HTTP status, response)."""
        try:
            if body.get("method") in TASK_METHODS:
                result = self._task_request(body, headers)
            else:
                result = self._call(self._admit(body, headers))
            return 200, success(body.get("id"), gateway_result(result))
        except Refusal as refusal:
            return refusal.status, error_response(body.get("id"), refusal.error)
        except ProtocolError as error:
            return http_status(error), error_response(body.get("id"), error)

    def open_stream(self, body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        """Answer one tools/call as request-scoped SSE.

        Returns (200, async iterator of SSE bytes) once the call is admitted, or
        (HTTP status, JSON-RPC error) when it is refused before anything is forwarded.
        When the client asked for progress, the backend request carries the gateway's own
        progress token, which is the backend request id.
        """
        try:
            admitted = self._admit(body, headers)
            backend_id = self._next_backend_id()
            backend_body, backend_headers = self._prepare(admitted, backend_id)
        except Refusal as refusal:
            return refusal.status, error_response(body.get("id"), refusal.error)
        except ProtocolError as error:
            return http_status(error), error_response(body.get("id"), error)
        token = admitted.params["_meta"].get("progressToken")
        if token is not None:
            backend_body["params"]["_meta"]["progressToken"] = backend_id
        backend = self.backends[admitted.route.backend]
        hop = Hop(admitted.request_id, backend_id, token, admitted.principal.key, backend.name)
        messages = self._tap(backend.stream(backend_body, backend_headers), admitted, backend.name, backend_id)
        return 200, relay(messages, hop, self.tasks)

    # -- admission ---------------------------------------------------------------

    def _authenticate(self, headers: dict[str, str]) -> Principal:
        scheme, _, token = headers.get("Authorization", "").partition(" ")
        principal = self.principals.get(token) if scheme == "Bearer" else None
        if principal is None:
            raise Refusal(401, ProtocolError(-32001, "Unauthenticated"))
        return principal

    def _validated(self, principal: Principal, body: dict[str, Any], headers: dict[str, str]) -> Admitted:
        params = validate_wire(body, headers)
        return Admitted(
            principal=principal,
            method=body["method"],
            request_id=body.get("id"),
            params=params,
            headers=dict(headers),
            capabilities=mediated(params["_meta"][CLIENT_CAPABILITIES_META], self.mediates),
            started=self.clock(),
        )

    def _admit(self, body: dict[str, Any], headers: dict[str, str]) -> Admitted:
        """Admit one tools/call, in this order: authenticate the caller, validate the wire
        (the routing headers must match the body), find the route, ask the policy, and
        only then spend one unit of the caller's rate limit. A refusal forwards nothing."""
        principal = self._authenticate(headers)
        request = self._validated(principal, body, headers)
        if request.method != "tools/call":
            raise ProtocolError(-32601, "Method not found")
        public = str(request.params.get("name"))
        route = self.routes.get(public)
        request = replace(request, public=public, route=route)
        if route is None:
            decision = Decision(False, "unknown_tool", None, "live")
        else:
            decision = self.policy.decide(self._context(request))
        outcome = "allow" if decision.allowed else "deny"
        if decision.allowed and not self._spend(principal, public):
            outcome = "rate_limit"
        self._audit_decision(request, decision, outcome)
        if outcome == "deny":
            raise Refusal(403, ProtocolError(-32003, "Forbidden", {"tool": public, "reason": decision.reason}))
        if outcome == "rate_limit":
            raise Refusal(429, ProtocolError(-32029, "Rate limited", {"tool": public}))
        return request

    def _context(self, request: Admitted) -> CallContext:
        route, principal = request.route, request.principal
        arguments = request.params.get("arguments")
        target = arguments.get(route.tenant_arg) if route.tenant_arg and isinstance(arguments, dict) else None
        return CallContext(
            principal=principal.id,
            issuer=principal.issuer,
            tenant=principal.tenant,
            token_roles=principal.roles,
            tool=request.public,
            backend=route.backend,
            operation=route.operation,
            classification=route.classification,
            target_tenant=target if isinstance(target, str) else None,
            admitted=route.admitted,
            pinned=route.pinned,
            healthy=self.backends[route.backend].healthy,
        )

    def _spend(self, principal: Principal, public: str) -> bool:
        """Spend one unit of the caller's rate limit for a public tool; False when its window is full."""
        route = self.routes.get(public)
        if route is None:
            return True
        key = LimitKey(principal.id, principal.issuer, principal.resource, public, route.operation)
        return self.limiter.allow(key, self.clock())

    # -- forwarding --------------------------------------------------------------

    def _next_backend_id(self) -> str:
        self._sent += 1
        return f"gw-{self._sent}"

    def _backend_request(self, request: Admitted, backend_id: str) -> tuple[dict[str, Any], dict[str, str]]:
        """The fresh, self-contained request the backend gets for one admitted call.

        Its params are the caller's (arguments, and MRTR inputResponses and requestState
        untouched) under the backend's own tool name, with the gateway's own _meta:
        protocol version, the gateway's clientInfo, and only the capabilities the
        gateway mediates and the caller declared. The gateway is the backend's client.
        Its headers are the routing headers plus the gateway's credential for that
        backend; nothing else of the caller's goes along.
        """
        params = dict(request.params, name=request.route.tool)
        params["_meta"] = request_meta(GATEWAY_INFO, request.capabilities)
        body = {"jsonrpc": "2.0", "id": backend_id, "method": "tools/call", "params": params}
        headers = {
            **routing_headers("tools/call", params),
            "Authorization": f"Bearer {self._credential(request.route.backend)}",
        }
        return body, headers

    def _credential(self, backend_name: str) -> str:
        """The gateway's own token for a backend's issuer and resource.

        A token is only ever presented to the issuer and resource it was issued for, and
        the caller's token never leaves the gateway: a backend without a credential is
        not called.
        """
        backend = self.backends[backend_name]
        token = self.credentials.get((backend.issuer, backend.resource))
        if token is None:
            raise ProtocolError(-32603, "No credential for backend", {"backend": backend_name})
        return token

    def _prepare(self, request: Admitted, backend_id: str) -> tuple[dict[str, Any], dict[str, str]]:
        try:
            return self._backend_request(request, backend_id)
        except ProtocolError as error:
            self._audit_result(request, request.route.backend, backend_id, None, error)
            raise

    def _call(self, request: Admitted) -> dict[str, Any]:
        backend = request.route.backend
        backend_id = self._next_backend_id()
        body, headers = self._prepare(request, backend_id)
        result = self._settle(self.backends[backend].handle(body, headers), request, backend, backend_id)
        if result.get("resultType") == "task":
            self.tasks.record(result["taskId"], request.principal.key, backend)
        return result

    def _settle(self, response: dict[str, Any], request: Admitted, backend: str, backend_id: str) -> dict[str, Any]:
        """Check and audit a backend's response; return the result the gateway may relay."""
        try:
            result = check_response(response, backend_id, request.capabilities, backend)
        except ProtocolError as error:
            self._audit_result(request, backend, backend_id, None, error)
            raise
        self._audit_result(request, backend, backend_id, result, None)
        return result

    async def _tap(
        self, messages: AsyncGenerator[dict[str, Any], None], request: Admitted, backend: str, backend_id: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """The backend's stream on its way to the relay: the response is checked and audited
        like a JSON answer, and a stream that ends without one ends with an error."""
        try:
            async for message in messages:
                if message.get("id") == backend_id and ("result" in message or "error" in message):
                    yield self._settled(message, request, backend, backend_id)
                    return
                yield message
            yield self._settled({"jsonrpc": "2.0", "id": backend_id}, request, backend, backend_id)
        finally:
            await messages.aclose()

    def _settled(self, response: dict[str, Any], request: Admitted, backend: str, backend_id: str) -> dict[str, Any]:
        try:
            return success(backend_id, self._settle(response, request, backend, backend_id))
        except ProtocolError as error:
            return error_response(backend_id, error)

    # -- tasks -------------------------------------------------------------------

    def _task_request(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Route tasks/get, tasks/update or tasks/cancel by the task id that Mcp-Name mirrors,
        to the backend that returned the task, for the principal it was returned to."""
        request = self._validated(self._authenticate(headers), body, headers)
        task_id = request.params.get("taskId")
        try:
            backend = self.tasks.resolve(task_id, request.principal.key)
        except TaskNotFound:
            self._audit_decision(request, Decision(False, "unknown_task", None, "live"), "deny")
            raise ProtocolError(-32602, "Task not found") from None
        self._audit_decision(request, Decision(True, "task_owner", None, "live"), "allow")
        backend_id = self._next_backend_id()
        forwarded = {key: value for key, value in request.params.items() if key != "_meta"}
        backend_body, backend_headers = make_request(
            request.method, backend_id, forwarded, client_info=GATEWAY_INFO, capabilities=request.capabilities
        )
        backend_headers["Authorization"] = f"Bearer {self._credential(backend)}"
        response = self.backends[backend].handle(backend_body, backend_headers)
        return self._settle(response, request, backend, backend_id)

    # -- audit -------------------------------------------------------------------

    def _ms(self) -> int:
        return round(self.clock() * 1000)

    def _audit_decision(self, request: Admitted, decision: Decision, outcome: str) -> None:
        params = request.params
        state = params.get("requestState")
        self.audit.record(
            {
                "kind": "decision",
                "ts": self._ms(),
                "principal": request.principal.id,
                "issuer": request.principal.issuer,
                "trace_id": trace_id_of(params["_meta"]),
                "request_id": request.request_id,
                "method": request.method,
                "tool": request.public,
                "task_id": params.get("taskId"),
                "state_in": state_digest(state) if isinstance(state, str) else None,
                "decision": outcome,
                "reason": decision.reason,
                "policy_version": decision.policy_version,
                "path": decision.path,
                "headers": request.headers,
                "arguments": params.get("arguments"),
                "inputResponses": params.get("inputResponses"),
            }
        )

    def _audit_result(
        self,
        request: Admitted,
        backend: str,
        backend_id: str,
        result: dict[str, Any] | None,
        error: ProtocolError | None,
    ) -> None:
        kind = "error" if result is None else result.get("resultType")
        self.audit.record(
            {
                "kind": "result",
                "ts": self._ms(),
                "principal": request.principal.id,
                "issuer": request.principal.issuer,
                "trace_id": trace_id_of(request.params["_meta"]),
                "request_id": request.request_id,
                "backend": backend,
                "backend_request_id": backend_id,
                "result": kind,
                "error": None if error is None else {"code": error.code, "message": error.message},
                "state_out": state_digest(result["requestState"]) if kind == "input_required" else None,
                "task_id": result.get("taskId") if kind == "task" else request.params.get("taskId"),
                "latency_ms": (self.clock() - request.started) * 1000,
            }
        )
