"""JSON-RPC 2.0 envelopes for MCP 2026-07-28: requests, results and errors."""
from __future__ import annotations

import copy
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = [PROTOCOL_VERSION]
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

# Over HTTP these headers mirror the body. Mcp-Name mirrors a different param per method.
VERSION_HEADER = "MCP-Protocol-Version"
METHOD_HEADER = "Mcp-Method"
NAME_HEADER = "Mcp-Name"
NAME_PARAMS = {
    "tools/call": "name",
    "prompts/get": "name",
    "resources/read": "uri",
    "tasks/get": "taskId",
    "tasks/update": "taskId",
    "tasks/cancel": "taskId",
}

CLIENT_INFO = {"name": "mcpcore-client", "version": "1.0.0"}
SERVER_INFO = {"name": "mcpcore-notes", "version": "1.0.0"}


def request_meta(
    version: str = PROTOCOL_VERSION,
    capabilities: dict[str, Any] | None = None,
    include_client_info: bool = True,
) -> dict[str, Any]:
    """The params._meta object of one request.

    capabilities defaults to an empty object: the client declares no optional capabilities.
    """
    meta: dict[str, Any] = {
        VERSION_KEY: version,
        CAPABILITIES_KEY: {} if capabilities is None else copy.deepcopy(capabilities),
    }
    if include_client_info:
        meta[CLIENT_INFO_KEY] = dict(CLIENT_INFO)
    return meta


def make_request(
    request_id: int | str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    version: str = PROTOCOL_VERSION,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one self-contained request that carries its own metadata in params._meta.

    The request shares no objects with params, with capabilities or with any other request.
    """
    body_params = copy.deepcopy(params) if params is not None else {}
    body_params["_meta"] = request_meta(version, capabilities)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}


def rpc_error(
    request_id: Any, code: int, message: str, data: Any | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def complete_result(
    payload: dict[str, Any], *, ttl_ms: int | None = None, cache_scope: str | None = None
) -> dict[str, Any]:
    """A successful result: resultType "complete", the payload, and the server's identity.

    Cacheable results pass ttl_ms; cache_scope then defaults to "private".
    """
    result = {"resultType": "complete", **payload, "_meta": {SERVER_INFO_KEY: dict(SERVER_INFO)}}
    if ttl_ms is not None:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = cache_scope or "private"
    return result


def unsupported_version(request_id: Any, version: str) -> dict[str, Any]:
    """The -32022 error for a version this server does not support."""
    return rpc_error(
        request_id,
        -32022,
        "Unsupported protocol version",
        {"requested": version, "supported": list(SUPPORTED_VERSIONS)},
    )


def validate_request(message: dict[str, Any]) -> dict[str, Any] | None:
    """Check one request's envelope and params._meta, outside any HTTP transport.

    Returns the JSON-RPC error response, or None when the request is valid. Structure comes
    first: -32600 for the envelope, -32602 for params and metadata. Only a well-formed request
    can be refused for its version (-32022). clientInfo is optional, but one that is present
    needs a string name and a string version.
    """
    request_id = message.get("id")
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return rpc_error(request_id, -32600, "Invalid Request")
    params = message.get("params")
    if not isinstance(params, dict):
        return rpc_error(request_id, -32602, "params must be an object")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return rpc_error(request_id, -32602, "params._meta must be an object")
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        return rpc_error(request_id, -32602, f"{VERSION_KEY} must be a string")
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        return rpc_error(request_id, -32602, f"{CAPABILITIES_KEY} must be an object")
    client_info = meta.get(CLIENT_INFO_KEY)
    if client_info is not None and not (
        isinstance(client_info, dict)
        and isinstance(client_info.get("name"), str)
        and isinstance(client_info.get("version"), str)
    ):
        return rpc_error(request_id, -32602, f"{CLIENT_INFO_KEY} needs a string name and version")
    if version not in SUPPORTED_VERSIONS:
        return unsupported_version(request_id, version)
    return None
