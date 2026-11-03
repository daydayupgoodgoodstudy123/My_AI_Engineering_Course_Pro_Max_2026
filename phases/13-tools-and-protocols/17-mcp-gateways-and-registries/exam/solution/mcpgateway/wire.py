"""MCP 2026-07-28 request envelopes, routing headers and result checks.

Shared by the gateway and the backends behind it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"
TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
TASK_METHODS = ("tasks/get", "tasks/update", "tasks/cancel")
NAMED_METHODS = ("tools/call", "resources/read", "prompts/get", *TASK_METHODS)

GATEWAY_INFO = {"name": "enterprise-gateway", "version": "2.0.0"}

# The client capability that each kind of embedded MRTR input request needs.
INPUT_CAPABILITIES = {
    "elicitation/create": "elicitation",
    "sampling/createMessage": "sampling",
    "roots/list": "roots",
}


@dataclass(frozen=True)
class ProtocolError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None


def request_meta(client_info: dict[str, str], capabilities: dict[str, Any]) -> dict[str, Any]:
    """A complete per-request _meta envelope."""
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META: capabilities,
        CLIENT_INFO_META: client_info,
    }


def request_name(method: str, params: dict[str, Any]) -> Any:
    """What Mcp-Name mirrors: params.taskId for the task methods, else params.name or params.uri."""
    if method in TASK_METHODS:
        return params.get("taskId")
    return params.get("name") or params.get("uri")


def routing_headers(method: str, params: dict[str, Any]) -> dict[str, str]:
    """The routing headers that mirror a request body."""
    headers = {"MCP-Protocol-Version": PROTOCOL_VERSION, "Mcp-Method": method}
    if method in NAMED_METHODS:
        headers["Mcp-Name"] = str(request_name(method, params) or "")
    return headers


def make_request(
    method: str,
    request_id: Any,
    params: dict[str, Any] | None = None,
    *,
    client_info: dict[str, str],
    capabilities: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """A JSON-RPC request with a full _meta envelope (plus any extra `meta` keys) and its routing headers."""
    wire_params = dict(params or {})
    wire_params["_meta"] = {**request_meta(client_info, capabilities), **(meta or {})}
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": wire_params}
    return body, routing_headers(method, wire_params)


def validate_wire(body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """Check one request and return its params.

    The order is fixed: JSON-RPC and metadata types (-32600, -32602), then header and
    body equality (-32020), then support for the version they agree on (-32022).
    """
    if body.get("jsonrpc") != "2.0":
        raise ProtocolError(-32600, "Invalid Request")
    method = body.get("method")
    params = body.get("params")
    if not isinstance(method, str) or not isinstance(params, dict):
        raise ProtocolError(-32600, "Invalid Request")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise ProtocolError(-32602, "params._meta is required")
    version = meta.get(PROTOCOL_META)
    if not isinstance(version, str):
        raise ProtocolError(-32602, "protocolVersion must be a string")
    if not isinstance(meta.get(CLIENT_CAPABILITIES_META), dict):
        raise ProtocolError(-32602, "clientCapabilities is required")
    if headers.get("MCP-Protocol-Version") != version:
        raise ProtocolError(-32020, "MCP-Protocol-Version header mismatch")
    if headers.get("Mcp-Method") != method:
        raise ProtocolError(-32020, "Mcp-Method header mismatch")
    if method in NAMED_METHODS and headers.get("Mcp-Name") != request_name(method, params):
        raise ProtocolError(-32020, "Mcp-Name header mismatch")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(
            -32022,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": version},
        )
    return params


def mediated(declared: dict[str, Any], supported: dict[str, Any]) -> dict[str, Any]:
    """The client capabilities a gateway declares to a backend for one request.

    Only what the gateway supports end to end and the caller declared; extensions are
    matched by name. The values are the gateway's own.
    """
    out: dict[str, Any] = {}
    for name, value in supported.items():
        if name == "extensions":
            theirs = declared.get("extensions")
            if isinstance(theirs, dict):
                common = {ext: cfg for ext, cfg in value.items() if isinstance(theirs.get(ext), dict)}
                if common:
                    out["extensions"] = common
        elif isinstance(declared.get(name), dict):
            out[name] = value
    return out


def check_response(
    response: dict[str, Any], backend_id: str, capabilities: dict[str, Any], backend: str
) -> dict[str, Any]:
    """The result of a backend's response to request `backend_id`, if the gateway can relay it.

    `capabilities` is what the gateway declared to the backend for this request. Raises
    ProtocolError(-32603) for an error response, an answer to another request, or a
    result the client could not take: input requests it did not declare, or a task
    without the Tasks extension.
    """
    if response.get("id") != backend_id:
        raise ProtocolError(-32603, "Backend answered another request", {"backend": backend})
    if "error" in response:
        raise ProtocolError(-32603, "Backend error", {"backend": backend, "error": response["error"]})
    result = response.get("result")
    if not isinstance(result, dict):
        raise ProtocolError(-32603, "Backend sent no result", {"backend": backend})
    kind = result.get("resultType")
    relayable = kind == "complete"
    if kind == "input_required":
        requests = result.get("inputRequests")
        relayable = (
            isinstance(requests, dict)
            and isinstance(result.get("requestState"), str)
            and all(
                isinstance(request, dict) and INPUT_CAPABILITIES.get(request.get("method")) in capabilities
                for request in requests.values()
            )
        )
    elif kind == "task":
        relayable = TASKS_EXTENSION in capabilities.get("extensions", {}) and isinstance(result.get("taskId"), str)
    if not relayable:
        raise ProtocolError(
            -32603,
            "Backend returned a result the gateway cannot relay",
            {"backend": backend, "resultType": kind},
        )
    return result


def gateway_result(result: dict[str, Any]) -> dict[str, Any]:
    """A backend result as the gateway returns it: the backend's _meta replaced by the gateway's serverInfo."""
    relayed = {key: value for key, value in result.items() if key != "_meta"}
    relayed["_meta"] = {SERVER_INFO_META: dict(GATEWAY_INFO)}
    return relayed


def success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, error: ProtocolError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        payload["data"] = error.data
    return {"jsonrpc": "2.0", "id": request_id, "error": payload}


def state_digest(state: str) -> str:
    """A short fingerprint of an opaque requestState, so the audit trail can link MRTR rounds."""
    return hashlib.sha256(state.encode("utf-8")).hexdigest()[:16]


def trace_id_of(meta: dict[str, Any]) -> str | None:
    """The trace id of a W3C traceparent in _meta ("00-<trace id>-<span id>-<flags>"), or None."""
    value = meta.get("traceparent")
    if isinstance(value, str):
        parts = value.split("-")
        if len(parts) == 4 and len(parts[1]) == 32:
            return parts[1]
    return None
