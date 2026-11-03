"""Wire constants and small helpers shared by the notes server, the connector and the client."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"
SERVER_INFO = {"name": "scopegate", "version": "1.0.0"}


@dataclass
class McpError(Exception):
    """A JSON-RPC error. dispatch() turns it into {"code", "message", "data"}."""

    code: int
    message: str
    data: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.code} {self.message}"


def request_meta(capabilities: dict[str, Any]) -> dict[str, Any]:
    """The _meta a 2026-07-28 client attaches to every request."""
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CAPABILITIES_META: capabilities,
        CLIENT_INFO_META: {"name": "scopegate-client", "version": "1.0.0"},
    }


def text(message: str) -> list[dict[str, str]]:
    return [{"type": "text", "text": message}]


def complete(**fields: Any) -> dict[str, Any]:
    """A finished result."""
    return {"resultType": "complete", **fields, "_meta": {SERVER_INFO_META: dict(SERVER_INFO)}}


def input_required(input_requests: dict[str, Any], request_state: str) -> dict[str, Any]:
    """An MRTR result: the client gathers these inputs and retries the same call with a fresh id."""
    return {
        "resultType": "input_required",
        "inputRequests": input_requests,
        "requestState": request_state,
        "_meta": {SERVER_INFO_META: dict(SERVER_INFO)},
    }


def validate_request_meta(params: dict[str, Any]) -> dict[str, Any]:
    """Check the metadata every 2026-07-28 request carries for itself, and return it."""
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise McpError(-32602, "missing request _meta")
    version = meta.get(PROTOCOL_META)
    if not isinstance(version, str):
        raise McpError(-32602, "missing protocol version")
    if version != PROTOCOL_VERSION:
        raise McpError(
            -32022,
            "unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": version},
        )
    if not isinstance(meta.get(CAPABILITIES_META), dict):
        raise McpError(-32602, "missing client capabilities")
    return meta


def supports_form_elicitation(capabilities: dict[str, Any]) -> bool:
    """Whether one request's client capabilities allow form-mode elicitation.

    "elicitation": {} still means form-only support, for compatibility, and
    "elicitation": {"form": {}} declares form mode explicitly. A URL-only
    declaration, "elicitation": {"url": {}}, does not support form mode.
    """
    elicitation = capabilities.get("elicitation")
    if not isinstance(elicitation, dict):
        return False
    return isinstance(elicitation.get("form", {}), dict)


def supports_url_elicitation(capabilities: dict[str, Any]) -> bool:
    """Whether one request's client capabilities allow URL-mode elicitation."""
    elicitation = capabilities.get("elicitation")
    return isinstance(elicitation, dict) and isinstance(elicitation.get("url"), dict)


def dispatch(
    request: dict[str, Any],
    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
) -> dict[str, Any] | None:
    """Route one JSON-RPC request to its handler.

    A request without an id is a notification: it is processed, but gets no response.
    """
    is_notification = "id" not in request
    request_id = request.get("id")
    try:
        params = request.get("params", {})
        if not isinstance(params, dict):
            raise McpError(-32602, "params must be an object")
        handler = handlers.get(request.get("method"))
        if handler is None:
            raise McpError(-32601, "method not found")
        result = handler(params)
    except McpError as exc:
        if is_notification:
            return None
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.data is not None:
            error["data"] = exc.data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}
    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
