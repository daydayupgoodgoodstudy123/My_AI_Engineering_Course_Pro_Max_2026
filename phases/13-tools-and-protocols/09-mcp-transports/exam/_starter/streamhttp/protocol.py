"""JSON-RPC and MCP 2026-07-28 pieces that the server and the client share."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = (PROTOCOL_VERSION,)
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
SERVER_INFO = {"name": "streamhttp", "version": "1.0.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
HEADER_MISMATCH = -32020
UNSUPPORTED_VERSION = -32022


class RpcFault(Exception):
    """A JSON-RPC error, raised where it is found and turned into a response at the edge."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass(frozen=True)
class Principal:
    """The caller, as the authentication layer in front of the endpoint identified it."""

    subject: str
    tenant: str


def rpc_error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def complete(
    payload: dict[str, Any], *, ttl_ms: int | None = None, cache_scope: str = "private"
) -> dict[str, Any]:
    """A finished result: resultType "complete", the payload, and the serverInfo stamp in _meta."""
    result = {"resultType": "complete", **payload, "_meta": {SERVER_INFO_KEY: dict(SERVER_INFO)}}
    if ttl_ms is not None:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = cache_scope
    return result


def validate_structure(message: dict[str, Any]) -> str:
    """Check the JSON-RPC envelope and the per-request _meta; return the body's protocol version.

    Every modern request and notification carries its protocol version and client capabilities
    in params._meta. Nothing is remembered from an earlier request.
    """
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        raise RpcFault(INVALID_REQUEST, "Invalid Request")
    params = message.get("params")
    if not isinstance(params, dict):
        raise RpcFault(INVALID_PARAMS, "params must be an object")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise RpcFault(INVALID_PARAMS, "params._meta is required")
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        raise RpcFault(INVALID_PARAMS, f"{VERSION_KEY} is required")
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        raise RpcFault(INVALID_PARAMS, f"{CAPABILITIES_KEY} is required")
    return version
