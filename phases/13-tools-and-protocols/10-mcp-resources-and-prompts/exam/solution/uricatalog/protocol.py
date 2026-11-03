"""The 2026-07-28 wire contract: per-request metadata, JSON-RPC errors and complete results."""
from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = "2026-07-28"
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
SUBSCRIPTION_ID_KEY = "io.modelcontextprotocol/subscriptionId"

SERVER_INFO = {"name": "uricatalog", "version": "1.0.0"}
CLIENT_INFO = {"name": "uricatalog-host", "version": "1.0.0"}

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
UNSUPPORTED_VERSION = -32022


class RpcError(Exception):
    """A request the server answers with a JSON-RPC error instead of a result."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def as_json(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


def request_meta() -> dict[str, Any]:
    """The _meta every request carries: there is no handshake to remember it for us."""
    return {
        VERSION_KEY: PROTOCOL_VERSION,
        CLIENT_INFO_KEY: dict(CLIENT_INFO),
        CAPABILITIES_KEY: {},
    }


def rpc_request(request_id: int | str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {**(params or {}), "_meta": request_meta()},
    }


def validate_meta(params: Any) -> None:
    """Check one request's own _meta. Nothing is carried over from earlier requests."""
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "params must be an object")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise RpcError(INVALID_PARAMS, "Missing request metadata")
    requested = meta.get(VERSION_KEY)
    if not isinstance(requested, str):
        raise RpcError(INVALID_PARAMS, "Missing or invalid protocol version")
    if requested != PROTOCOL_VERSION:
        raise RpcError(
            UNSUPPORTED_VERSION,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        raise RpcError(INVALID_PARAMS, "Missing client capabilities")


def complete(payload: dict[str, Any], *, ttl_ms: int | None = None, cache_scope: str | None = None) -> dict[str, Any]:
    """A successful result: resultType "complete", the payload, optional cache hints, serverInfo."""
    result: dict[str, Any] = {"resultType": "complete", **payload}
    if ttl_ms is not None:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = cache_scope
    result["_meta"] = {SERVER_INFO_KEY: dict(SERVER_INFO)}
    return result


def notification(method: str, subscription_id: int | str, **params: Any) -> dict[str, Any]:
    """A notification on a subscription stream; its _meta names the subscription."""
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": {"_meta": {SUBSCRIPTION_ID_KEY: subscription_id}, **params},
    }
