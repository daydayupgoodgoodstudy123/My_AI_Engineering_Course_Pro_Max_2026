"""Wire pieces of stateless MCP 2026-07-28 shared by the server and the host."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"


@dataclass
class McpError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None


def request_meta(*, sampling: bool = True, client: str = "lesson-client") -> dict[str, Any]:
    """The _meta every request carries: protocol version, client capabilities and client info."""
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CAPABILITIES_META: {"sampling": {}} if sampling else {},
        CLIENT_INFO_META: {"name": client, "version": "1.0.0"},
    }


def validate_request_meta(params: dict[str, Any]) -> dict[str, Any]:
    """Check the per-request metadata and return it."""
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


def canonical(value: Any) -> bytes:
    """Sorted, compact JSON: equal values always give the same bytes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def server_meta() -> dict[str, Any]:
    return {SERVER_INFO_META: {"name": "mrtrkit", "version": "1.0.0"}}


def complete(**fields: Any) -> dict[str, Any]:
    return {"resultType": "complete", **fields, "_meta": server_meta()}


def input_required(requests: dict[str, Any], state: str) -> dict[str, Any]:
    return {
        "resultType": "input_required",
        "inputRequests": requests,
        "requestState": state,
        "_meta": server_meta(),
    }


def sampling_request(prompt: str, preferences: dict[str, float], max_tokens: int = 400) -> dict[str, Any]:
    """An embedded sampling/createMessage request.

    modelPreferences are independent hints for the client's model policy; they need not sum to 1.
    """
    return {
        "method": "sampling/createMessage",
        "params": {
            "messages": [{"role": "user", "content": {"type": "text", "text": prompt}}],
            "systemPrompt": "Return only the requested value.",
            "modelPreferences": dict(preferences),
            "includeContext": "none",
            "maxTokens": max_tokens,
        },
    }


def sampling_text(responses: Any, key: str) -> str:
    """The text of the sampling answer stored under key in inputResponses."""
    if not isinstance(responses, dict):
        raise McpError(-32602, "inputResponses must be an object")
    response = responses.get(key)
    if not isinstance(response, dict):
        raise McpError(-32602, f"missing input response: {key}")
    content = response.get("content")
    if not isinstance(content, dict) or content.get("type") != "text":
        raise McpError(-32602, f"invalid sampling response: {key}")
    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        raise McpError(-32602, f"empty sampling response: {key}")
    return text


def error_response(request_id: Any, exc: McpError) -> dict[str, Any]:
    error: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.data is not None:
        error["data"] = exc.data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}
