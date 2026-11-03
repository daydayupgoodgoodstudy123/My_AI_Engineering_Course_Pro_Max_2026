"""MCP 2026-07-28 request envelopes, built the way the lesson builds them, and the JSON-RPC error type."""
from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = "2026-07-28"
APPS_EXTENSION = "io.modelcontextprotocol/ui"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"
RESOURCE_MIME = "text/html;profile=mcp-app"
HOST_INFO = {"name": "lesson-host", "version": "1.0.0"}

# Methods whose Mcp-Name header mirrors params.name or params.uri.
NAMED_METHODS = ("tools/call", "resources/read", "prompts/get")


class ProtocolError(Exception):
    """A JSON-RPC error: code, message and optional data."""

    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(f"{code} {message}")
        self.code = code
        self.message = message
        self.data = data


def request_meta(*, apps: bool = True) -> dict[str, Any]:
    """The metadata every request carries: protocol version, client capabilities, client info."""
    extensions = {APPS_EXTENSION: {}} if apps else {}
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META: {"extensions": extensions},
        CLIENT_INFO_META: dict(HOST_INFO),
    }


def make_request(
    method: str,
    request_id: Any,
    params: dict[str, Any] | None = None,
    *,
    apps: bool = True,
) -> tuple[dict[str, Any], dict[str, str]]:
    """A complete, self-contained request body and its Streamable HTTP routing headers."""
    body_params = dict(params or {})
    body_params["_meta"] = request_meta(apps=apps)
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}
    headers = {"MCP-Protocol-Version": PROTOCOL_VERSION, "Mcp-Method": method}
    if method in NAMED_METHODS:
        headers["Mcp-Name"] = str(body_params.get("name") or body_params.get("uri") or "")
    return body, headers
