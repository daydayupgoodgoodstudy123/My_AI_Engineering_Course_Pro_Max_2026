"""One replica of the MCP endpoint: an HTTP request in, an HTTP response out."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .drafts import DraftStore, UnknownHandle, VersionConflict
from .protocol import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    SUPPORTED_VERSIONS,
    UNSUPPORTED_VERSION,
    Principal,
    RpcFault,
    complete,
    rpc_error,
    validate_structure,
)
from .wire import Headers, Readable, check_mirrored_headers, read_body

ENDPOINT = "/mcp"
DEFAULT_ORIGINS = ("http://localhost", "http://127.0.0.1", "https://client.example")

TOOLS = [
    {
        "name": "draft_create",
        "description": "Start a draft. Returns its handle; pass the handle to the other draft tools.",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "draft_read",
        "description": "Read a draft by its handle.",
        "inputSchema": {
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "draft_save",
        "description": "Replace a draft's text. version is the version you last read.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "version": {"type": "integer"},
                "text": {"type": "string"},
            },
            "required": ["handle", "version", "text"],
        },
    },
    {
        "name": "ping",
        "description": "Return pong for a transport health check.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "idempotentHint": True},
    },
]


@dataclass
class HttpRequest:
    method: str
    path: str
    headers: list[tuple[str, str]]
    body: Readable
    principal: Principal | None = None  # set by the authentication layer in front of the endpoint


@dataclass
class HttpResponse:
    status: int
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""

    def header(self, name: str) -> str | None:
        """A response header by case-insensitive name, or None."""
        for key, value in self.headers:
            if key.lower() == name.lower():
                return value
        return None


def json_response(status: int, payload: dict[str, Any]) -> HttpResponse:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return HttpResponse(status, [("Content-Type", "application/json")], body)


class StreamableServer:
    """One replica of the endpoint.

    It keeps nothing between requests: each request carries its own protocol context, and drafts
    live in the shared store under handles that the client sends back.
    """

    def __init__(self, drafts: DraftStore, *, allowed_origins: Iterable[str] = DEFAULT_ORIGINS) -> None:
        self.drafts = drafts
        self.allowed_origins = frozenset(allowed_origins)

    def handle(self, request: HttpRequest) -> HttpResponse:
        """Answer one HTTP request. The first rule that applies decides the response.

        1. A path other than ENDPOINT: 404 without a JSON-RPC body.
        2. An Origin header that is present but not exactly one of allowed_origins: 403. A request
           without Origin, as a non-browser client may send it, passes.
        3. Any method but POST: 405 with Allow: POST.
        4. A body read_body refuses, or one that is not JSON: 400 with -32700 and a null id.
        5. A message validate_structure refuses: 400 with its error.
        6. Mirrored headers that check_mirrored_headers refuses: 400 with -32020.
        7. A version that header and body agree on but this server does not support: 400 with
           -32022 and data {"supported": SUPPORTED_VERSIONS as a list, "requested": that version}.
        8. A notification (no id): 202 with an empty body, whatever its method.
        9. Otherwise dispatch(message, request.principal). An unknown method is 404 with the
           -32601 error as the body, so a dual-era client can tell a modern server from a missing
           endpoint. Every other response is 200.

        JSON bodies go out with Content-Type: application/json. Mcp-Session-Id and Last-Event-ID
        are ignored, and no response carries Mcp-Session-Id.
        """
        headers = Headers(request.headers)
        if request.path != ENDPOINT:
            return HttpResponse(404)
        origins = headers.get_all("Origin")
        if origins and (len(origins) > 1 or origins[0] not in self.allowed_origins):
            return HttpResponse(403)
        if request.method != "POST":
            return HttpResponse(405, [("Allow", "POST")])
        try:
            message = json.loads(read_body(headers, request.body))
        except ValueError as exc:  # FramingError, JSONDecodeError and UnicodeDecodeError
            return json_response(400, rpc_error(None, PARSE_ERROR, "Parse error", {"detail": str(exc)}))
        if not isinstance(message, dict):
            return json_response(400, rpc_error(None, INVALID_REQUEST, "Invalid Request"))
        request_id = message.get("id")
        try:
            version = validate_structure(message)
            check_mirrored_headers(headers, message)
            if version not in SUPPORTED_VERSIONS:
                raise RpcFault(
                    UNSUPPORTED_VERSION,
                    "Unsupported protocol version",
                    {"supported": list(SUPPORTED_VERSIONS), "requested": version},
                )
        except RpcFault as fault:
            return json_response(400, rpc_error(request_id, fault.code, str(fault), fault.data))
        if "id" not in message:
            return HttpResponse(202)
        response = self.dispatch(message, request.principal)
        status = 404 if response.get("error", {}).get("code") == METHOD_NOT_FOUND else 200
        return json_response(status, response)

    def dispatch(self, message: dict[str, Any], principal: Principal | None) -> dict[str, Any]:
        """Run one checked request and return its JSON-RPC response. An unknown method is -32601."""
        request_id = message["id"]
        method = message["method"]
        try:
            if method == "server/discover":
                result = complete(
                    {"supportedVersions": list(SUPPORTED_VERSIONS), "capabilities": {"tools": {}}},
                    ttl_ms=3_600_000,
                    cache_scope="public",
                )
            elif method == "tools/list":
                result = complete({"tools": TOOLS}, ttl_ms=30_000, cache_scope="public")
            elif method == "tools/call":
                result = self._call_tool(message["params"], principal)
            else:
                raise RpcFault(METHOD_NOT_FOUND, f"Method not found: {method}")
        except RpcFault as fault:
            return rpc_error(request_id, fault.code, str(fault), fault.data)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _call_tool(self, params: dict[str, Any], principal: Principal | None) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise RpcFault(INVALID_PARAMS, "arguments must be an object")
        if name == "ping":
            return _tool_text("pong")
        if name not in ("draft_create", "draft_read", "draft_save"):
            return _tool_text(f"Unknown tool: {name}", is_error=True)
        if principal is None:
            return _tool_text("draft tools need an authenticated caller", is_error=True)
        try:
            if name == "draft_create":
                draft = self.drafts.create(principal, _string(arguments, "text"))
            elif name == "draft_read":
                draft = self.drafts.get(principal, _string(arguments, "handle"))
                return _tool_json({"handle": draft.handle, "version": draft.version, "text": draft.text})
            else:
                version = arguments.get("version")
                if type(version) is not int:
                    raise ValueError("version must be an integer")
                handle, text = _string(arguments, "handle"), _string(arguments, "text")
                draft = self.drafts.save(principal, handle, text, expected_version=version)
        except UnknownHandle:
            return _tool_text("unknown or expired draft handle", is_error=True)
        except VersionConflict as conflict:
            return _tool_text(f"the draft changed; read version {conflict.current} and retry", is_error=True)
        except ValueError as exc:
            return _tool_text(str(exc), is_error=True)
        return _tool_json({"handle": draft.handle, "version": draft.version})


def _string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return complete({"content": [{"type": "text", "text": text}], "isError": is_error})


def _tool_json(payload: dict[str, Any]) -> dict[str, Any]:
    return _tool_text(json.dumps(payload, ensure_ascii=False))
