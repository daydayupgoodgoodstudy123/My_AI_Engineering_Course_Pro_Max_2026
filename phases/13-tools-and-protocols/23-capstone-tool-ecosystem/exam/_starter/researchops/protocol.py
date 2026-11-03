"""Wire shapes for MCP revision 2026-07-28, as this simulation uses them.

A request is {"method": str, "params": {..., "_meta": {...}}}. A response is either a result,
which carries resultType and the server's identity under _meta, or
{"error": {"code": int, "message": str, "data": ...}}.
"""
from __future__ import annotations

PROTOCOL_VERSION = "2026-07-28"
TASKS = "io.modelcontextprotocol/tasks"

VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

CLIENT_INFO = {"name": "researchops-agent", "version": "1.0.0"}

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
MISSING_CAPABILITY = -32021
UNSUPPORTED_VERSION = -32022


def request_meta(*, tasks: bool = False) -> dict:
    """Fresh params._meta for one request: protocol version, client capabilities, client identity.

    tasks=True declares the Tasks extension in this request's capabilities.
    """
    extensions = {TASKS: {}} if tasks else {}
    return {
        VERSION_KEY: PROTOCOL_VERSION,
        CAPABILITIES_KEY: {"extensions": extensions},
        CLIENT_INFO_KEY: dict(CLIENT_INFO),
    }


def error(code: int, message: str, data: dict | None = None) -> dict:
    body: dict = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return {"error": body}


def check_meta(meta: object, *, require_tasks: bool = False) -> dict | None:
    """Check one request's _meta on the server side: an error response, or None when it is valid."""
    if not isinstance(meta, dict):
        return error(INVALID_PARAMS, "params._meta must be an object")
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        return error(INVALID_PARAMS, "protocolVersion must be a string")
    if version != PROTOCOL_VERSION:
        return error(
            UNSUPPORTED_VERSION,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": version},
        )
    capabilities = meta.get(CAPABILITIES_KEY)
    if not isinstance(capabilities, dict):
        return error(INVALID_PARAMS, "clientCapabilities must be an object")
    extensions = capabilities.get("extensions", {})
    if require_tasks and (not isinstance(extensions, dict) or TASKS not in extensions):
        return error(
            MISSING_CAPABILITY,
            "Missing required client capability",
            {"requiredCapabilities": {"extensions": {TASKS: {}}}},
        )
    return None


def unwrap(response: dict) -> dict:
    """The result a response carries. An error response raises ProtocolError."""
    if "error" in response:
        raise ProtocolError.from_response(response)
    return response


class ProtocolError(Exception):
    """A JSON-RPC error response, raised on the client side."""

    def __init__(self, code: int, message: str, data: object = None) -> None:
        detail = f" {data}" if data is not None else ""
        super().__init__(f"{code} {message}{detail}")
        self.code = code
        self.message = message
        self.data = data

    @classmethod
    def from_response(cls, response: dict) -> "ProtocolError":
        body = response["error"]
        return cls(body["code"], body["message"], body.get("data"))
