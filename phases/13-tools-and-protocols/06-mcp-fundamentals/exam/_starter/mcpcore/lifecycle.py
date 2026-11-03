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
    raise NotImplementedError
