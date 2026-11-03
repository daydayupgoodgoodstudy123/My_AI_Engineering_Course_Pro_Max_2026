"""The checks one incoming message goes through before any handler runs."""
from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import Any

from .capabilities import missing_capabilities
from .wire import (
    CAPABILITIES_KEY,
    CLIENT_INFO_KEY,
    METHOD_HEADER,
    NAME_HEADER,
    NAME_PARAMS,
    SUPPORTED_VERSIONS,
    VERSION_HEADER,
    VERSION_KEY,
    rpc_error,
    unsupported_version,
)

METHODS = frozenset({"server/discover", "tools/list", "tools/call"})


def check_request(
    body: bytes,
    headers: Mapping[str, str] | None = None,
    *,
    methods: Collection[str] = METHODS,
    required: Mapping[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Run the request lifecycle checks on one incoming message, in this order:

    1. The body must parse as JSON (-32700) and be one JSON object (-32600). Both errors
       carry a null id.
    2. A message without an "id" member is a notification. Outside HTTP (headers is None)
       it never gets a response, however malformed it is. Over HTTP it goes through checks
       3 to 5 like a request, with a null id in any error, and gets no response if it
       passes them.
    3. jsonrpc must be "2.0" and method a string (-32600). params must be an object, and
       params._meta an object with a string protocol version and an object of client
       capabilities. clientInfo is optional, but a present one needs a string name and
       version. Any of these wrong is -32602.
    4. headers holds the HTTP request headers, or is None when the message did not come
       over HTTP. Over HTTP, MCP-Protocol-Version must equal the body's version and
       Mcp-Method its method; for a method in NAME_PARAMS, Mcp-Name must equal that param.
       A missing or different header is -32020, even when one of the two versions is one
       the server does not support.
    5. Only then is the version checked: -32022, with data {"requested", "supported"}.
    6. A method in required needs the client capabilities listed there; what the request
       does not declare, as missing_capabilities computes it, is -32021 with data
       {"requiredCapabilities": ...}. A method not in methods is -32601.

    Returns the error response for the first check that fails, echoing the request id, or
    None when there is no error to send back.
    """
    try:
        message = json.loads(body)
    except ValueError:
        return rpc_error(None, -32700, "Parse error")
    if not isinstance(message, dict):
        return rpc_error(None, -32600, "Invalid Request: expected one JSON object")
    notification = "id" not in message
    if notification and headers is None:
        return None
    request_id = message.get("id")
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
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
    capabilities = meta.get(CAPABILITIES_KEY)
    if not isinstance(capabilities, dict):
        return rpc_error(request_id, -32602, f"{CAPABILITIES_KEY} must be an object")
    client_info = meta.get(CLIENT_INFO_KEY)
    if client_info is not None and not (
        isinstance(client_info, dict)
        and isinstance(client_info.get("name"), str)
        and isinstance(client_info.get("version"), str)
    ):
        return rpc_error(request_id, -32602, f"{CLIENT_INFO_KEY} needs a string name and version")

    if headers is not None:
        mirrored = [(VERSION_HEADER, version), (METHOD_HEADER, method)]
        if method in NAME_PARAMS:
            mirrored.append((NAME_HEADER, params.get(NAME_PARAMS[method])))
        for header, body_value in mirrored:
            value = headers.get(header)
            if value is None or value != body_value:
                return rpc_error(request_id, -32020, f"{header} does not match the request body")

    if version not in SUPPORTED_VERSIONS:
        return unsupported_version(request_id, version)

    if notification:
        return None
    needs = (required or {}).get(method)
    if needs is not None:
        missing = missing_capabilities(needs, capabilities)
        if missing:
            return rpc_error(
                request_id,
                -32021,
                "Missing required client capability",
                {"requiredCapabilities": missing},
            )
    if method not in methods:
        return rpc_error(request_id, -32601, f"Method not found: {method}")
    return None
