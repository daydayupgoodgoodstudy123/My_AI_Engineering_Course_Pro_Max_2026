"""The 2026-07-28 wire contract: per-request metadata, JSON-RPC errors and typed results."""
from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = (PROTOCOL_VERSION,)
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

SERVER_INFO = {"name": "notesrv", "version": "2.0.0"}
MAX_SAFE_INTEGER = 2**53 - 1


class RpcProblem(Exception):
    """A request the server answers with a JSON-RPC error instead of a result."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


def rpc_error(request_id: int | str | None, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def valid_request_id(value: Any) -> bool:
    """Supplied id boundary: strings or integers, with bool excluded.

    Integers must lie within ±(2**53 - 1): the TypeScript port keeps ids in JavaScript
    numbers, and both servers have to accept exactly the same ids.
    """
    if isinstance(value, str):
        return True
    return type(value) is int and -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER


def complete(
    payload: dict[str, Any],
    *,
    ttl_ms: int | None = None,
    cache_scope: str = "private",
) -> dict[str, Any]:
    """Wrap a successful payload as a modern result.

    Every success gets resultType "complete" and the server identity in result _meta.
    Discovery, list and read handlers pass ttl_ms, which adds ttlMs and cacheScope. The scope
    defaults to "private", the safe choice for anything user-specific. Every other result
    goes out without cache hints.
    """
    result = {
        "resultType": "complete",
        **payload,
        "_meta": {SERVER_INFO_KEY: dict(SERVER_INFO)},
    }
    if ttl_ms is not None:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = cache_scope
    return result


def validate_request(message: dict[str, Any]) -> None:
    """Check one request's envelope and its own params._meta; raise RpcProblem on a problem.

    Nothing is carried over from earlier requests: each request must bring its protocol
    version and client capabilities. clientInfo is optional, but must be well formed if sent.
    """
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        raise RpcProblem(-32600, "Invalid Request")
    if not valid_request_id(message.get("id")):
        raise RpcProblem(-32600, "id must be a string or a safe integer")
    params = message.get("params")
    if not isinstance(params, dict):
        raise RpcProblem(-32602, "params must be an object")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise RpcProblem(-32602, "params._meta is required")
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        raise RpcProblem(-32602, f"{VERSION_KEY} is required")
    if version not in SUPPORTED_VERSIONS:
        raise RpcProblem(
            -32022,
            "Unsupported protocol version",
            {"requested": version, "supported": list(SUPPORTED_VERSIONS)},
        )
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        raise RpcProblem(-32602, f"{CAPABILITIES_KEY} is required")
    info = meta.get(CLIENT_INFO_KEY)
    if info is not None and not (
        isinstance(info, dict)
        and isinstance(info.get("name"), str)
        and isinstance(info.get("version"), str)
    ):
        raise RpcProblem(-32602, f"{CLIENT_INFO_KEY} is malformed")
