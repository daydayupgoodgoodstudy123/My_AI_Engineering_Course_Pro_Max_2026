import asyncio
import base64
import copy
import hashlib
import hmac
import json
import random
import time
from dataclasses import replace

import pytest
from mcpgateway.audit import AuditLog, MemoryAudit
from mcpgateway.backends import Backend
from mcpgateway.chain import reconstruct
from mcpgateway.gateway import Gateway, Principal, Route
from mcpgateway.limits import LimitKey, RateLimiter
from mcpgateway.policy import CallContext, Decision, Policy, PolicyEngine, PolicyUnavailable, RolePolicy
from mcpgateway.relay import Hop, TaskNotFound, TaskRoutes, relay
from mcpgateway.wire import (
    CLIENT_CAPABILITIES_META,
    CLIENT_INFO_META,
    GATEWAY_INFO,
    PROTOCOL_META,
    PROTOCOL_VERSION,
    SERVER_INFO_META,
    TASKS_EXTENSION,
    ProtocolError,
    make_request,
    success,
)

IDP = "https://idp.example"
PARTNER_IDP = "https://partner-idp.example"
RESOURCE = "https://gateway.example/mcp"
AUTH = "https://auth.example"
ALICE, BOB, PARTNER_ALICE = (IDP, "alice"), (IDP, "bob"), (PARTNER_IDP, "alice")
AGENT = {"name": "alice-agent", "version": "0.9.1"}


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def raises(error, action, *args) -> bool:
    try:
        action(*args)
    except error:
        return True
    return False


def drain(agen) -> list:
    async def run() -> list:
        return [item async for item in agen]

    return asyncio.run(run())


def parse_sse(raw: bytes) -> list[dict]:
    """The client's SSE reader: every event is one `data: <JSON>` line and a blank line."""
    text = raw.decode("utf-8")
    assert text.endswith("\n\n"), "every event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        lines = block.split("\n")
        assert len(lines) == 1 and lines[0].startswith("data: "), f"each event is a single data line, got {block[:60]!r}"
        events.append(json.loads(lines[0][len("data: ") :]))
    return events


async def next_events(stream, count: int) -> bytes:
    """Read the client's stream until `count` whole events have arrived."""
    raw = b""
    while raw.count(b"\n\n") < count:
        raw += await stream.__anext__()
    return raw


def progress(token, value, total=None, message=None) -> dict:
    params = {"progressToken": token, "progress": value}
    if total is not None:
        params["total"] = total
    if message is not None:
        params["message"] = message
    return {"jsonrpc": "2.0", "method": "notifications/progress", "params": params}


def respond(request_id, result: dict, server: str = "reports") -> dict:
    """A backend's response, with the backend's own serverInfo."""
    return success(
        request_id, {**result, "_meta": {SERVER_INFO_META: {"name": server, "version": "1.4.0"}, "com.example/shard": "eu-2"}}
    )


def relayed(request_id, result: dict) -> dict:
    """The same result as the gateway relays it."""
    return success(request_id, {**result, "_meta": {SERVER_INFO_META: GATEWAY_INFO}})


# -- the backends behind the gateway ------------------------------------------------

STATE_KEY = b"notes-state-key"
ASK = {
    "confirm": {
        "method": "elicitation/create",
        "params": {
            "mode": "form",
            "message": "Publish the Q3 summary — café edition?",
            "requestedSchema": {"type": "object", "properties": {"publish": {"type": "boolean"}}, "required": ["publish"]},
        },
    }
}
ANSWER = {"confirm": {"action": "accept", "content": {"publish": True}}}
DONE = {"resultType": "complete", "content": [{"type": "text", "text": "Q3 report ready"}], "isError": False}
TASK = {
    "taskId": "tsk-7c1e",
    "status": "working",
    "createdAt": "2026-11-01T09:30:00Z",
    "lastUpdatedAt": "2026-11-01T09:30:00Z",
    "ttlMs": 900000,
    "pollIntervalMs": 1000,
}


def sign(claims: dict) -> str:
    """The notes backend's requestState: base64url claims plus an HMAC over them."""
    body = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode()).decode()
    return body + "." + hmac.new(STATE_KEY, body.encode(), hashlib.sha256).hexdigest()


def summarize(params: dict) -> dict:
    state = params.get("requestState")
    if state is None:
        return {"resultType": "input_required", "inputRequests": ASK, "requestState": sign({"doc": params["arguments"]["doc"]})}
    body, _, mac = state.rpartition(".")
    if not hmac.compare_digest(mac, hmac.new(STATE_KEY, body.encode(), hashlib.sha256).hexdigest()):
        raise ProtocolError(-32602, "requestState does not verify")
    doc = json.loads(base64.urlsafe_b64decode(body))["doc"]
    publish = params["inputResponses"]["confirm"]["content"]["publish"]
    return {"content": [{"type": "text", "text": f"{doc} published: {publish}"}], "isError": False}


def build(params: dict) -> dict:
    """The backend alone decides: a task when the request declares the Tasks extension."""
    if TASKS_EXTENSION in params["_meta"][CLIENT_CAPABILITIES_META].get("extensions", {}):
        return {"resultType": "task", **TASK}
    quarter = params["arguments"]["quarter"]
    return {"content": [{"type": "text", "text": f"{quarter} report ready"}], "isError": False}


def get_task(params: dict) -> dict:
    if params["taskId"] != TASK["taskId"]:
        raise ProtocolError(-32602, "Task not found")
    return dict(TASK)


def streamed(tool, server):
    """A request-scoped stream: progress for the request's token, then the response."""

    def start(request_id, params):
        async def messages():
            token = params["_meta"].get("progressToken")
            if token is not None:
                yield progress(token, 1, 2)
                yield progress(token, 2, 2)
            yield respond(request_id, {"resultType": "complete", **tool(params)}, server)

        return messages()

    return start


def build_gateway(clock, *, policy=None, audit=None, mediates=None):
    notes = Backend(
        "notes",
        issuer=AUTH,
        resource="https://notes.example/mcp",
        token="notes-secret",
        tools={
            "search": lambda params: {"content": [{"type": "text", "text": "2 notes"}], "isError": False},
            "create": lambda params: {"content": [{"type": "text", "text": "created"}], "isError": False},
            "summarize": summarize,
        },
        streams={"summarize": streamed(summarize, "notes")},
    )
    reports = Backend(
        "reports",
        issuer=AUTH,
        resource="https://reports.example/mcp",
        token="reports-secret",
        tools={"build": build, "tasks/get": get_task},
        streams={"build": streamed(build, "reports")},
    )
    legacy = Backend("legacy", issuer="https://legacy-auth.example", resource="https://legacy.example/mcp", token="legacy-secret")
    backends = {backend.name: backend for backend in (notes, reports, legacy)}
    gateway = Gateway(
        principals={
            "tok-alice": Principal("alice", IDP, RESOURCE, "acme", frozenset({"developer"})),
            "tok-bob": Principal("bob", IDP, RESOURCE, "acme", frozenset({"auditor"})),
            "tok-partner": Principal("alice", PARTNER_IDP, RESOURCE, "globex", frozenset({"developer"})),
        },
        routes={
            "notes.search": Route("notes", "search", "read", "public"),
            "notes.create": Route("notes", "create", "write"),
            "notes.summarize": Route("notes", "summarize", "read"),
            "reports.build": Route("reports", "build", "read"),
            "legacy.export": Route("legacy", "export", "read"),
        },
        backends=backends,
        credentials={
            (AUTH, "https://notes.example/mcp"): "notes-secret",
            (AUTH, "https://reports.example/mcp"): "reports-secret",
        },
        policy=policy
        or RolePolicy(
            {
                "notes.search": {"developer", "auditor"},
                "notes.create": {"developer"},
                "notes.summarize": {"developer"},
                "reports.build": {"developer"},
                "legacy.export": {"developer"},
            }
        ),
        limiter=RateLimiter({"read": 3, "write": 1}, window_s=60.0),
        audit=audit if audit is not None else MemoryAudit(),
        clock=clock,
        mediates=mediates if mediates is not None else {"elicitation": {}},
    )
    return gateway, backends


def request(token, method, request_id, params, *, caps=None, meta=None, extra=None):
    """A client request: a full _meta envelope, its routing headers and the caller's bearer token."""
    body, headers = make_request(
        method, request_id, params, client_info=AGENT, capabilities={} if caps is None else caps, meta=meta
    )
    headers["Authorization"] = f"Bearer {token}"
    headers.update(extra or {})
    return body, headers


def call(gateway, token, method, request_id, params, **kwargs):
    return gateway.handle(*request(token, method, request_id, params, **kwargs))


def search(gateway, token, request_id):
    return call(gateway, token, "tools/call", request_id, {"name": "notes.search", "arguments": {"query": "plan"}})[0]


@pytest.mark.skip("Part 1")
def test_forward_call() -> None:
    """An admitted call reaches its backend as the gateway's own fresh request, within the caller's rate limit."""
    clock = Clock()
    gateway, backends = build_gateway(clock)
    reports, notes, legacy = backends["reports"], backends["notes"], backends["legacy"]
    declared = {"elicitation": {}, "sampling": {}, "extensions": {TASKS_EXTENSION: {}}}
    body, headers = request(
        "tok-alice",
        "tools/call",
        7,
        {"name": "reports.build", "arguments": {"quarter": "Q3"}},
        caps=declared,
        meta={"com.example/session": "s-41"},
        extra={"Mcp-Session-Id": "legacy-41", "Cookie": "sid=41"},
    )
    as_sent = copy.deepcopy((body, headers))
    status, reply = gateway.handle(body, headers)
    assert status == 200, f"an allowed call returns the backend's result, got {status} {reply.get('error')}"
    assert reply == relayed(7, DONE), "the client gets the backend's result under its own id, with the gateway's serverInfo"
    (sent,) = reports.received
    assert sent.body == {
        "jsonrpc": "2.0",
        "id": "gw-1",
        "method": "tools/call",
        "params": {
            "name": "build",
            "arguments": {"quarter": "Q3"},
            "_meta": {
                PROTOCOL_META: PROTOCOL_VERSION,
                CLIENT_CAPABILITIES_META: {"elicitation": {}},
                CLIENT_INFO_META: GATEWAY_INFO,
            },
        },
    }, "the backend gets a fresh request: a new id, its own tool name, and the gateway's _meta with only the capabilities the gateway mediates"
    assert sent.headers == {
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": "tools/call",
        "Mcp-Name": "build",
        "Authorization": "Bearer reports-secret",
    }, "the backend gets the routing headers and the gateway's own credential, nothing of the caller's"
    assert (body, headers) == as_sent, "the gateway leaves the caller's request alone"

    status, reply = call(gateway, "tok-bob", "tools/call", "b-1", {"name": "notes.search", "arguments": {"query": "plan"}})
    assert status == 200, f"an allowed call returns the backend's result, got {status} {reply.get('error')}"
    assert notes.received[-1].headers["Authorization"] == "Bearer notes-secret", "each backend gets the token for its own resource"
    assert notes.received[-1].body["params"]["_meta"][CLIENT_CAPABILITIES_META] == {}, (
        "nothing is declared for a caller that declared nothing"
    )
    status, reply = call(gateway, "tok-alice", "tools/call", 8, {"name": "legacy.export", "arguments": {}})
    assert status == 502 and legacy.received == [], "a backend the gateway holds no credential for is never called"

    first = {"name": "notes.summarize", "arguments": {"doc": "Q3 summary"}}
    status, asked = call(gateway, "tok-alice", "tools/call", 9, first, caps={"elicitation": {}})
    assert status == 200 and asked["result"]["resultType"] == "input_required", (
        f"an MRTR round reaches a client that declared elicitation, got {status} {asked.get('error')}"
    )
    retry = {**first, "inputResponses": ANSWER, "requestState": asked["result"]["requestState"]}
    status, done = call(gateway, "tok-alice", "tools/call", 10, retry, caps={"elicitation": {}})
    assert done.get("result", {}).get("content") == [{"type": "text", "text": "Q3 summary published: True"}], (
        f"an MRTR retry reaches the backend with its inputResponses and requestState, got {status} {done.get('error')}"
    )

    for broken in ("method header", "tool name", "version"):
        body, headers = request("tok-alice", "tools/call", f"x-{broken}", {"name": "notes.search", "arguments": {}})
        if broken == "method header":
            headers["Mcp-Method"] = "tools/list"
        elif broken == "tool name":
            body["params"]["name"] = "notes.searcher"
        else:
            body["params"]["_meta"][PROTOCOL_META] = headers["MCP-Protocol-Version"] = "2025-11-25"
        assert gateway.handle(body, headers)[0] == 400, f"a malformed request is refused: {broken}"
    forwarded = len(notes.received)
    statuses = [search(gateway, "tok-alice", 20 + i) for i in range(4)]
    assert statuses == [200, 200, 200, 429], (
        f"refused requests do not spend the caller's quota of 3 reads a minute, got {statuses}"
    )
    assert len(notes.received) == forwarded + 3, "a rate-limited call is not forwarded"
    denied = [
        call(gateway, "tok-bob", "tools/call", f"b-w{i}", {"name": "notes.create", "arguments": {"title": "x"}})[0]
        for i in range(3)
    ]
    assert denied == [403, 403, 403], f"a call the policy refuses is forbidden every time and spends nothing, got {denied}"

    assert search(gateway, "tok-bob", "b-2") == 200, "each principal has its own quota"
    assert search(gateway, "tok-partner", 30) == 200, "the same subject at another issuer is another principal"
    status, _ = call(gateway, "tok-alice", "tools/call", 31, {"name": "reports.build", "arguments": {"quarter": "Q4"}})
    assert status == 200, "each tool has its own quota"
    writes = [
        call(gateway, "tok-alice", "tools/call", 40 + i, {"name": "notes.create", "arguments": {"title": "x"}})[0]
        for i in range(2)
    ]
    assert writes == [200, 429], "writes have their own, smaller quota"

    clock.now = 1030.0
    assert search(gateway, "tok-alice", 50) == 429, "an allowed call counts for the whole window"
    clock.now = 1059.9
    assert search(gateway, "tok-alice", 51) == 429, "an allowed call counts for the whole window"
    clock.now = 1060.0
    statuses = [search(gateway, "tok-alice", 52 + i) for i in range(4)]
    assert statuses == [200, 200, 200, 429], (
        f"a call stops counting window_s after it was allowed, and refused calls never count, got {statuses}"
    )

    limiter = RateLimiter({"read": 12_000, "write": 100}, window_s=60.0)
    key = LimitKey("batch-job", IDP, RESOURCE, "notes.search", "read")
    start = time.perf_counter()
    allowed = [limiter.allow(key, 5000.0 + i / 1000) for i in range(12_001)]
    elapsed = time.perf_counter() - start
    assert allowed.count(True) == 12_000 and allowed[-1] is False, "a key gets exactly its quota in a window"
    assert elapsed < 0.05, "checking a rate limit should not rescan the whole window"


REPLICA = {
    "kind": "decision",
    "ts": 1_793_525_399_870,
    "principal": "zoë",
    "issuer": PARTNER_IDP,
    "trace_id": None,
    "request_id": "r-1",
    "method": "tools/call",
    "tool": "notes.search",
    "task_id": None,
    "state_in": None,
    "decision": "deny",
    "reason": "role",
    "policy_version": "v7",
    "path": "live",
    "headers": ["Authorization", "MCP-Protocol-Version"],
    "arguments": {"query": "naïve plan"},
    "inputResponses": None,
    "seq": 1,
}
DECISION = {
    "kind": "decision",
    "ts": 1_793_525_400_123,
    "principal": "alice",
    "issuer": IDP,
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "request_id": 7,
    "method": "tools/call",
    "tool": "vault.store",
    "task_id": None,
    "state_in": "9f86d081884c7d65",
    "decision": "allow",
    "reason": "allowed",
    "policy_version": "v12",
    "path": "live",
    "headers": {
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": "tools/call",
        "Mcp-Name": "vault.store",
        "Authorization": "Bearer tok-alice-7f3a",
        "Cookie": "sid=COOKIE-9d2",
    },
    "arguments": {
        "name": "deploy-key",
        "Password": "PW-5e1",
        "options": {"refresh_token": "RT-88a", "note": "rotate monthly"},
        "items": [{"api_key": "AK-41c"}, "plain"],
        "secret": {"kid": "k-1", "value": "SV-3b0"},
        "count": 3,
        "max_tokens": 512,
    },
    "inputResponses": {"login": {"action": "accept", "content": {"code": "AUTHCODE-17", "remember": True}}},
}
STORED = {
    **DECISION,
    "headers": ["Authorization", "Cookie", "MCP-Protocol-Version", "Mcp-Method", "Mcp-Name"],
    "arguments": {
        "name": "deploy-key",
        "Password": "[redacted]",
        "options": {"refresh_token": "[redacted]", "note": "rotate monthly"},
        "items": [{"api_key": "[redacted]"}, "plain"],
        "secret": "[redacted]",
        "count": 3,
        "max_tokens": 512,
    },
    "inputResponses": {"login": {"action": "accept", "content": {"code": "[redacted]", "remember": True}}},
    "seq": 2,
}
RESULT = {
    "kind": "result",
    "ts": 1_793_525_400_101,
    "principal": "alice",
    "issuer": IDP,
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "request_id": "7",
    "backend": "vault",
    "backend_request_id": "gw-3",
    "result": "error",
    "error": {"code": -32603, "message": "Backend error"},
    "state_out": None,
    "task_id": None,
    "latency_ms": 0.1 + 0.2,
}


@pytest.mark.skip("Part 2")
def test_audit_log(tmp_path) -> None:
    """Audit events are redacted before they reach the disk, and read back exactly, in the order written."""
    path = tmp_path / "audit.jsonl"
    path.write_bytes(json.dumps(REPLICA, ensure_ascii=False).encode("utf-8") + b"\n")  # another replica's line
    log = AuditLog(path)
    before = copy.deepcopy(DECISION)
    stored = log.record(DECISION)
    assert DECISION == before, "recording an event leaves the caller's dict alone"
    assert stored.get("seq") == 2, "an event is numbered after the events already in the file"
    assert stored == STORED, (
        "an event is stored as given, except that header values are dropped and secrets in arguments and inputResponses are redacted"
    )
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 2, "each event is one line, on disk by the time record returns"
    for secret in (b"tok-alice-7f3a", b"COOKIE-9d2", b"PW-5e1", b"RT-88a", b"AK-41c", b"SV-3b0", b"AUTHCODE-17"):
        assert secret not in raw, f"no secret reaches the disk: {secret.decode()}"

    log.record(RESULT)
    log.close()
    reopened = AuditLog(path)
    assert reopened.events() == [REPLICA, STORED, {**RESULT, "seq": 3}], (
        "a reopened log reads back every event exactly, in the order written"
    )
    assert reopened.record({**RESULT, "request_id": 8})["seq"] == 4, "numbering continues after a reopen"
    reopened.close()
    again = AuditLog(path)
    assert [event["seq"] for event in again.events()] == [1, 2, 3, 4]
    again.close()

    # Each already assembled event keeps enough evidence to understand this one hop.
    evidence_path = tmp_path / "single-events.jsonl"
    evidence_log = AuditLog(evidence_path)
    common = {
        "kind": "exchange", "ts": 1_793_525_401_000,
        "principal": "alice", "issuer": IDP,
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "request_id": 0,
        "backend_request_id": "gw-mrtr-2", "method": "tools/call",
        "tool": "notes.summarize", "backend": "notes",
        "descriptor_pin": {"version": "2.3.0", "digest": "a" * 64},
        "decision": "allow", "reason": "allowed", "policy_version": "v17", "path": "live",
        "latency_ms": 0.1 + 0.2,
        "request_meta": {PROTOCOL_META: PROTOCOL_VERSION, CLIENT_INFO_META: AGENT},
        "result_meta": {SERVER_INFO_META: {"name": "notes-backend", "version": "2.3.0"}},
        "headers": {"Mcp-Method": "tools/call", "Authorization": "Bearer SECRET-AUDIT17"},
        "arguments": {"code": "SECRET-CODE17", "count": 0,
                      "options": {"refresh_token": "SECRET-REFRESH17", "note": "keep"}},
        "inputResponses": {"summary": {"action": "accept", "content": {
            "code": "SECRET-ANSWER17", "items": [{"token": "SECRET-TOKEN17", "request_id": "payload-id"}]}}},
    }
    samples = [
        {**copy.deepcopy(common), "result": "input_required", "mrtr_round": 2,
         "state_in": "1" * 64, "state_out": "2" * 64, "task_id": None, "error": None},
        {**copy.deepcopy(common), "request_id": "0", "backend_request_id": "gw-task-3",
         "result": "task", "mrtr_round": None, "state_in": None, "state_out": None,
         "task_id": "task-audit-17", "error": None},
        {**copy.deepcopy(common), "request_id": 8, "backend_request_id": "gw-error-4",
         "result": "error", "result_meta": None, "mrtr_round": None, "task_id": None,
         "error": {"code": -32021, "message": "Missing required client capability",
                   "data": {"requiredCapabilities": {"extensions": {TASKS_EXTENSION: {}}}}}},
        {**copy.deepcopy(common), "kind": "decision", "request_id": 9,
         "backend_request_id": None, "result_meta": None, "result": "refused", "latency_ms": 0.0,
         "decision": "deny", "reason": "role", "mrtr_round": 0, "task_id": None,
         "error": {"code": -32003, "message": "Forbidden", "data": {"tool": "notes.summarize"}}},
    ]
    expected_events = []
    for number, event in enumerate(samples, start=1):
        before = copy.deepcopy(event)
        expected = {
            **copy.deepcopy(event), "seq": number, "headers": ["Authorization", "Mcp-Method"],
            "arguments": {"code": "[redacted]", "count": 0,
                          "options": {"refresh_token": "[redacted]", "note": "keep"}},
            "inputResponses": {"summary": {"action": "accept", "content": {
                "code": "[redacted]", "items": [{"token": "[redacted]", "request_id": "payload-id"}]}}},
        }
        expected_events.append(expected)
        assert evidence_log.record(event) == expected, (
            "one audit projection preserves MRTR, task, error, denial and source metadata while redacting only secrets"
        )
        assert event == before, "projecting protocol evidence leaves the source event unchanged"
        raw = evidence_path.read_bytes()
        assert b"SECRET-" not in raw, "no secret in a protocol audit event reaches the given sink"
        assert json.loads(raw.split(b"\n")[-2]) == expected, (
            "each single-event evidence projection is readable before close"
        )
    evidence_log.close()
    evidence_reopened = AuditLog(evidence_path)
    assert evidence_reopened.events() == expected_events, (
        "single-event protocol and policy evidence survives a reopen without type or metadata loss"
    )
    evidence_reopened.close()

    gateway_log = tmp_path / "gateway.jsonl"
    gateway, _ = build_gateway(Clock(), audit=AuditLog(gateway_log))
    status, _ = call(
        gateway, "tok-alice", "tools/call", 9, {"name": "notes.search", "arguments": {"query": "plan", "api_key": "AK-LIVE-2"}}
    )
    assert status == 200
    gateway.audit.close()
    raw = gateway_log.read_bytes()
    for secret in (b"tok-alice", b"notes-secret", b"AK-LIVE-2"):
        assert secret not in raw, f"the gateway's audit trail holds no credentials: {secret.decode()}"
    trail = AuditLog(gateway_log)
    assert [(event["kind"], event["request_id"], event["seq"]) for event in trail.events()] == [
        ("decision", 9, 1),
        ("result", 9, 2),
    ]
    trail.close()


V1 = Policy(
    version="v1",
    roles={ALICE: frozenset({"developer"}), BOB: frozenset({"auditor"})},
    tool_roles={
        "notes.search": frozenset({"developer", "auditor"}),
        "notes.create": frozenset({"developer"}),
        "notes.share": frozenset({"developer"}),
        "notes.summarize": frozenset({"developer"}),
        "docs.read": frozenset({"developer"}),
    },
    stale_reads=frozenset({"notes.search"}),
)


class PolicyService:
    """The policy service behind the engine. The test edits its document and takes it down."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.down = False

    def __call__(self) -> Policy:
        if self.down:
            raise PolicyUnavailable("policy service timed out")
        return self.policy


def context(**changes) -> CallContext:
    """alice reading public notes in her own tenant, on a healthy, admitted, pinned backend."""
    base = CallContext(
        principal="alice",
        issuer=IDP,
        tenant="acme",
        token_roles=frozenset({"developer"}),
        tool="notes.search",
        backend="notes",
        operation="read",
        classification="public",
        target_tenant=None,
        admitted=True,
        pinned=True,
        healthy=True,
    )
    return replace(base, **changes)


@pytest.mark.skip("Part 3")
def test_runtime_policy() -> None:
    """Every call is decided from the live policy; an outage fails closed except for approved public reads."""
    service, clock = PolicyService(V1), Clock(5000.0)
    engine = PolicyEngine(service, clock, last_known_ttl_s=30.0)
    allowed = Decision(True, "allowed", "v1", "live")
    assert engine.decide(context()) == allowed, "alice may search public notes in her own tenant"
    assert engine.decide(context(principal="bob", token_roles=frozenset({"auditor"}))) == allowed, "so may bob"
    assert engine.decide(context(admitted=False)) == Decision(False, "admission", "v1", "live"), (
        "a backend that is not admitted is not callable"
    )
    share = context(tool="notes.share", operation="write", classification="internal", target_tenant="globex")
    assert engine.decide(share) == Decision(False, "tenant", "v1", "live"), (
        "an approved, pinned tool still may not reach into another tenant"
    )
    assert engine.decide(replace(share, target_tenant="acme")) == allowed, "a call inside the principal's tenant is fine"
    assert engine.decide(context(classification="sensitive")) == allowed, (
        "sensitive data only changes what happens when the policy service is down"
    )
    assert engine.decide(context(pinned=False)) == Decision(False, "pin", "v1", "live"), "a changed descriptor is not callable"
    assert engine.decide(context(healthy=False)) == Decision(False, "health", "v1", "live"), "an unhealthy backend gets no calls"
    assert engine.decide(context(principal="carol", admitted=False)).reason == "admission", "the rules apply in order"
    assert engine.decide(context(pinned=False, target_tenant="globex")).reason == "pin", "the rules apply in order"
    assert engine.decide(context(target_tenant="globex", healthy=False)).reason == "tenant", "the rules apply in order"
    assert engine.decide(context(tool="tickets.close")) == Decision(False, "role", "v1", "live"), (
        "a tool the policy does not list is denied"
    )
    assert engine.decide(context(principal="carol")) == Decision(False, "role", "v1", "live"), (
        "a principal the policy does not list has no roles, whatever its token claims"
    )
    assert engine.decide(context(principal="carol", pinned=False)).reason == "role", "the rules apply in order"
    assert engine.decide(context(issuer=PARTNER_IDP)) == Decision(False, "role", "v1", "live"), (
        "roles belong to a principal at its issuer"
    )

    service.policy = replace(V1, version="v2", roles={ALICE: frozenset(), BOB: frozenset({"auditor"})})
    assert engine.decide(context()) == Decision(False, "role", "v2", "live"), (
        "a revoked role is denied at once, though the backend is still admitted and the token still claims the role"
    )
    service.policy = replace(V1, version="v3", quarantined=frozenset({"notes"}))
    write = context(tool="notes.create", operation="write", classification="internal")
    assert engine.decide(write) == Decision(False, "quarantine", "v3", "live")
    assert engine.decide(replace(write, healthy=False)).reason == "health", "the rules apply in order"
    assert engine.decide(context()) == Decision(True, "allowed", "v3", "live"), "a quarantine holds writes only"

    service.policy = replace(V1, version="v4", roles={ALICE: frozenset({"developer"}), BOB: frozenset()})
    assert engine.decide(context()) == Decision(True, "allowed", "v4", "live"), "the live policy decides while it answers"
    service.down = True
    clock.now = 5010.0
    assert engine.decide(context()) == Decision(True, "allowed", "v4", "last_known"), (
        "an approved public read may run on the last-known policy for a short while"
    )
    assert engine.decide(context(principal="bob", token_roles=frozenset({"auditor"}))) == Decision(
        False, "role", "v4", "last_known"
    ), "the last-known policy is applied in full"
    assert engine.decide(context(healthy=False)) == Decision(False, "health", "v4", "last_known"), (
        "the last-known policy is applied in full"
    )
    closed = Decision(False, "policy_unavailable", None, "fail_closed")
    for name, ctx in (
        ("a write", write),
        ("a write through an approved tool", context(operation="write")),
        ("a sensitive read", context(classification="sensitive")),
        ("an internal read", context(classification="internal")),
        ("a public read that is not approved", context(tool="docs.read")),
    ):
        assert engine.decide(ctx) == closed, f"{name} fails closed while the policy service is down"
    clock.now = 5029.9
    assert engine.decide(context()).path == "last_known", "the last-known policy serves until it is ttl old"
    clock.now = 5030.0
    assert engine.decide(context()) == closed, "once the last-known policy is ttl old, public reads fail closed too"

    service.down = False
    clock.now = 5040.0
    assert engine.decide(context(healthy=False)) == Decision(False, "health", "v4", "live"), (
        "the live policy decides while it answers"
    )
    service.down = True
    for now in (5050.0, 5060.0, 5069.9):
        clock.now = now
        assert engine.decide(context()).path == "last_known", "the ttl counts from the last fetch that worked"
    clock.now = 5070.0
    assert engine.decide(context()) == closed, "a failed fetch does not refresh the last-known policy"

    service, clock = PolicyService(V1), Clock()
    gateway, backends = build_gateway(clock, policy=PolicyEngine(service, clock))
    first = {"name": "notes.summarize", "arguments": {"doc": "Q3 summary"}}
    status, asked = call(gateway, "tok-alice", "tools/call", 21, first, caps={"elicitation": {}})
    assert status == 200 and asked["result"]["resultType"] == "input_required"
    service.policy = replace(V1, version="v2", roles={ALICE: frozenset(), BOB: frozenset({"auditor"})})
    retry = {**first, "inputResponses": ANSWER, "requestState": asked["result"]["requestState"]}
    status, refused = call(gateway, "tok-alice", "tools/call", 22, retry, caps={"elicitation": {}})
    assert (status, refused.get("error", {}).get("data", {}).get("reason")) == (403, "role"), (
        "every MRTR round is authorized again"
    )
    assert len(backends["notes"].received) == 1, "a refused retry is not forwarded"
    assert gateway.audit.events[-1]["policy_version"] == "v2"


@pytest.mark.skip("Part 4")
def test_sse_relay() -> None:
    """Backend streams reach the client as SSE under the client's own ids, and the tasks they return stay routable."""
    late: list[bool] = []

    async def indexer():
        yield progress("gw-3", 1, 3, "indexing for gw-3 — café")
        yield {"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "debug"}}
        yield {"jsonrpc": "2.0", "id": "srv-1", "method": "sampling/createMessage", "params": {"messages": []}}
        yield respond("gw-2", DONE)
        yield progress("gw-9", 1)
        yield progress("gw-3", 2, 3)
        yield respond("gw-3", DONE)
        late.append(True)
        yield progress("gw-3", 3, 3)

    hop = Hop(client_id=7, backend_id="gw-3", progress_token="p-7", owner=ALICE, backend="reports")
    chunks = drain(relay(indexer(), hop, TaskRoutes()))
    assert chunks and all(isinstance(chunk, bytes) for chunk in chunks), "the stream is written as bytes"
    assert parse_sse(b"".join(chunks)) == [
        progress("p-7", 1, 3, "indexing for gw-3 — café"),
        progress("p-7", 2, 3),
        relayed(7, DONE),
    ], "this request's progress under the client's token, then the response under the client's id"
    assert late == [], "the stream ends with the response; the backend is not read any further"

    async def quiet():
        yield progress("gw-4", 1)
        yield respond("gw-4", DONE)

    events = parse_sse(b"".join(drain(relay(quiet(), Hop("c-9", "gw-4", None, ALICE, "reports"), TaskRoutes()))))
    assert events == [relayed("c-9", DONE)], "a client that asked for no progress gets none"
    events = parse_sse(b"".join(drain(relay(quiet(), Hop(0, "gw-4", 0, ALICE, "reports"), TaskRoutes()))))
    assert events == [progress(0, 1), relayed(0, DONE)], "0 is a client id and a progress token like any other"

    async def failing():
        yield {"jsonrpc": "2.0", "id": "gw-5", "error": {"code": -32603, "message": "Backend error"}}

    events = parse_sse(b"".join(drain(relay(failing(), Hop(5, "gw-5", "p-5", ALICE, "reports"), TaskRoutes()))))
    assert events == [{"jsonrpc": "2.0", "id": 5, "error": {"code": -32603, "message": "Backend error"}}], (
        "an error response reaches the client under its own id too"
    )

    ask = {"resultType": "input_required", "inputRequests": ASK, "requestState": sign({"doc": "Q3 summary"})}

    async def asking():
        yield respond("gw-6", ask, "notes")

    events = parse_sse(b"".join(drain(relay(asking(), Hop(11, "gw-6", None, ALICE, "notes"), TaskRoutes()))))
    assert events == [relayed(11, ask)], "an input_required result passes through untouched, requestState and all"

    pulled: list[int] = []
    closed: list[bool] = []

    async def crawler():
        try:
            for page in range(1, 1000):
                pulled.append(page)
                yield progress("gw-7", page)
                await asyncio.sleep(0)
        finally:
            closed.append(True)

    async def first_then_hang_up():
        stream = relay(crawler(), Hop(12, "gw-7", "p-12", ALICE, "notes"), TaskRoutes())
        first = await next_events(stream, 1)
        seen = list(pulled)
        await stream.aclose()
        return first, seen, list(closed)

    first, seen, closed_now = asyncio.run(first_then_hang_up())
    assert parse_sse(first) == [progress("p-12", 1)], "the first event is the first progress"
    assert seen == [1], "progress is relayed as soon as it arrives"
    assert closed_now == [True], "a client that hangs up cancels the backend request"

    tasks = TaskRoutes()

    async def task_stream():
        yield progress("gw-8", 1)
        yield respond("gw-8", {"resultType": "task", **TASK})
        yield progress("gw-8", 2)

    async def take_task_then_hang_up():
        stream = relay(task_stream(), Hop(13, "gw-8", "p-13", ALICE, "reports"), tasks)
        got = await next_events(stream, 2)
        routed = not raises(TaskNotFound, tasks.resolve, TASK["taskId"], ALICE)
        await stream.aclose()
        return got, routed

    got, routed = asyncio.run(take_task_then_hang_up())
    assert parse_sse(got) == [progress("p-13", 1), relayed(13, {"resultType": "task", **TASK})]
    assert routed, "a task is routable before the client sees its taskId"
    assert not raises(TaskNotFound, tasks.resolve, TASK["taskId"], ALICE), "a task stays routable after the client hangs up"
    assert tasks.resolve(TASK["taskId"], ALICE) == "reports", "the route names the backend that holds the task"
    for owner, task_id in ((BOB, TASK["taskId"]), (PARTNER_ALICE, TASK["taskId"]), (ALICE, "tsk-0000")):
        assert raises(TaskNotFound, tasks.resolve, task_id, owner), f"only the task's owner reaches it: {owner}, {task_id}"

    gateway, backends = build_gateway(Clock(), mediates={"elicitation": {}, "extensions": {TASKS_EXTENSION: {}}})
    with_tasks = {"extensions": {TASKS_EXTENSION: {}}}
    status, stream = gateway.open_stream(
        *request(
            "tok-alice",
            "tools/call",
            31,
            {"name": "reports.build", "arguments": {"quarter": "Q4"}},
            caps=with_tasks,
            meta={"progressToken": "p-31"},
        )
    )
    assert status == 200
    events = parse_sse(b"".join(drain(stream)))
    assert events == [progress("p-31", 1, 2), progress("p-31", 2, 2), relayed(31, {"resultType": "task", **TASK})]
    status, reply = call(gateway, "tok-alice", "tasks/get", 32, {"taskId": TASK["taskId"]}, caps=with_tasks)
    assert (status, reply.get("result", {}).get("status")) == (200, "working"), (
        f"tasks/get reaches the backend that holds the task, got {status} {reply.get('error')}"
    )
    assert backends["reports"].received[-1].headers["Mcp-Name"] == TASK["taskId"]
    refusals = [
        call(gateway, token, "tasks/get", 33, {"taskId": task_id}, caps=with_tasks)
        for token, task_id in (("tok-bob", TASK["taskId"]), ("tok-partner", TASK["taskId"]), ("tok-alice", "tsk-0000"))
    ]
    assert refusals[0] == refusals[1] == refusals[2] and refusals[0][1]["error"]["code"] == -32602, (
        "someone else's task looks exactly like a task that does not exist"
    )

    first = {"name": "notes.summarize", "arguments": {"doc": "Q3 summary"}}
    status, stream = gateway.open_stream(*request("tok-alice", "tools/call", 41, first, caps={"elicitation": {}}))
    (asked,) = parse_sse(b"".join(drain(stream)))
    retry = {**first, "inputResponses": ANSWER, "requestState": asked["result"]["requestState"]}
    status, stream = gateway.open_stream(*request("tok-alice", "tools/call", 42, retry, caps={"elicitation": {}}))
    (done,) = parse_sse(b"".join(drain(stream)))
    assert done == relayed(42, {"resultType": "complete", "content": [{"type": "text", "text": "Q3 summary published: True"}], "isError": False}), (
        f"the backend accepts the requestState the client echoed, got {done.get('error')}"
    )


T1, T2, T3, T9 = ("1" * 32, "2" * 32, "3" * 32, "9" * 32)


def decision(seq, ts, who, trace, request_id, *, method="tools/call", state_in=None, task_id=None, outcome="allow"):
    issuer, principal = who
    return {
        "kind": "decision",
        "seq": seq,
        "ts": ts,
        "principal": principal,
        "issuer": issuer,
        "trace_id": trace,
        "request_id": request_id,
        "method": method,
        "tool": "notes.summarize" if method == "tools/call" else None,
        "task_id": task_id,
        "state_in": state_in,
        "decision": outcome,
        "reason": "allowed" if outcome == "allow" else "role",
        "policy_version": "v1",
        "path": "live",
    }


def result(seq, ts, who, trace, request_id, *, kind="complete", state_out=None, task_id=None):
    issuer, principal = who
    return {
        "kind": "result",
        "seq": seq,
        "ts": ts,
        "principal": principal,
        "issuer": issuer,
        "trace_id": trace,
        "request_id": request_id,
        "backend": "notes",
        "backend_request_id": f"gw-{seq}",
        "result": kind,
        "error": None,
        "state_out": state_out,
        "task_id": task_id,
        "latency_ms": 2.5,
    }


CHAIN = [
    decision(1, 100, ALICE, T1, 1),
    decision(2, 100, ALICE, T2, 1),  # a second agent run, reusing request id 1
    result(3, 105, ALICE, T1, 1, kind="input_required", state_out="s-a1"),
    result(4, 108, ALICE, T2, 1),
    decision(5, 103, BOB, T1, 1),  # bob's service, called inside alice's trace, also starts at 1
    result(6, 120, BOB, T1, 1),
    decision(7, 130, ALICE, T1, 2, state_in="s-a1"),  # the MRTR retry: a new id
    result(8, 134, ALICE, T1, 2, kind="input_required", state_out="s-a2"),
    decision(9, 101, ALICE, T1, 4),  # another call in the same trace, logged late
    result(10, 150, ALICE, T1, 4),
    decision(11, 160, ALICE, T1, 3, state_in="s-a2"),
    result(12, 166, ALICE, T1, 3, kind="task", task_id="tsk-1"),
    decision(13, 170, BOB, T3, 2, state_in="s-a1", outcome="deny"),  # bob replays alice's state
    result(14, 175, ALICE, T9, 77),  # its decision is not in the log
    decision(15, 120, ALICE, T1, 5, state_in="s-a1"),  # round 2 sent twice
    result(16, 181, ALICE, T1, 5, kind="error"),
    decision(17, 185, ALICE, T1, 6, state_in="s-zzz"),  # a state nobody issued
    result(18, 188, ALICE, T1, 6),
    decision(19, 900, ALICE, T2, 7, method="tasks/get", task_id="tsk-1"),  # much later, from another trace
    result(20, 903, ALICE, T2, 7, task_id="tsk-1"),
    decision(21, 905, BOB, T3, 3, method="tasks/get", task_id="tsk-1", outcome="deny"),  # bob polls alice's task
    decision(22, 1500, ALICE, T2, 9, method="tasks/get", task_id="tsk-1"),
    result(23, 1500, ALICE, T2, 9, task_id="tsk-1"),
    decision(24, 1600, ALICE, T2, 10, method="tasks/cancel", task_id="tsk-1"),
    result(25, 1601, ALICE, T2, 10, task_id="tsk-1"),
    decision(26, 1700, ALICE, T2, 11, state_in="s-a2", outcome="deny"),  # round 3 again from a new trace, refused
    decision(27, 132, PARTNER_ALICE, T1, 2, state_in="s-a1", outcome="deny"),  # alice at the partner IdP replays alice's state
]


def shape(node) -> tuple:
    return (node.event["seq"], [shape(child) for child in node.children])


@pytest.mark.skip("Part 5")
def test_decision_chain() -> None:
    """Flat audit events fold back into one tree per public call; what cannot be placed is an orphan."""
    events = copy.deepcopy(CHAIN)
    random.Random(17).shuffle(events)
    forest = reconstruct(events)
    assert [shape(call) for call in forest.calls] == [
        (1, [(3, []), (15, [(16, [])]), (7, [(8, []), (11, [(12, []), (19, [(20, [])]), (22, [(23, [])]), (24, [(25, [])])]), (26, [])])]),
        (2, [(4, [])]),
        (9, [(10, [])]),
        (5, [(6, [])]),
    ], "one tree per call: results under their requests, MRTR retries under the round they answer, task requests under the call that made the task"
    assert [shape(orphan) for orphan in forest.orphans] == [(27, []), (13, []), (14, []), (17, [(18, [])]), (21, [])], (
        "events that belong to no call are orphans: another principal's state or task, a missing decision, an unknown state"
    )
    assert forest.calls[0].event == CHAIN[0], "nodes hold the events"

    clock = Clock()
    gateway, _ = build_gateway(clock)
    trace = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    first = {"name": "notes.summarize", "arguments": {"doc": "Q3 summary"}}
    _, asked = call(gateway, "tok-alice", "tools/call", 1, first, caps={"elicitation": {}}, meta=trace)
    clock.now += 0.25
    call(gateway, "tok-alice", "tools/call", 2, {"name": "notes.search", "arguments": {"query": "plan"}}, meta=trace)
    clock.now += 0.25
    retry = {**first, "inputResponses": ANSWER, "requestState": asked["result"]["requestState"]}
    call(gateway, "tok-alice", "tools/call", 3, retry, caps={"elicitation": {}}, meta=trace)
    forest = reconstruct(gateway.audit.events)
    assert [shape(call) for call in forest.calls] == [(1, [(2, []), (5, [(6, [])])]), (3, [(4, [])])], (
        "the gateway's own audit trail folds back into its calls"
    )
    assert forest.orphans == []
