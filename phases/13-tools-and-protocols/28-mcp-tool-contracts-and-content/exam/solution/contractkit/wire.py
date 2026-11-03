"""JSON-RPC envelopes and the MCP 2026-07-28 request metadata every module shares."""
from __future__ import annotations

import re
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"

INVALID_PARAMS = -32602
HEADER_MISMATCH = -32020

# HTTP field-name token: one or more tchar.
HEADER_TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")


class ContractViolation(ValueError):
    """A descriptor, arguments, result, header or archived record breaks the contract."""


class McpError(Exception):
    """A JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.data = data


def request_meta() -> dict[str, Any]:
    """The _meta every request carries. Requests are stateless: none relies on an earlier one."""
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CAPABILITIES_META: {"completions": {}},
        CLIENT_INFO_META: {"name": "contractkit", "version": "1.0.0"},
    }


def make_request(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    """A JSON-RPC request whose params carry this client's _meta."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {**params, "_meta": request_meta()},
    }


def complete(**fields: Any) -> dict[str, Any]:
    """A server result: resultType complete, the given fields, then the server's _meta."""
    return {
        "resultType": "complete",
        **fields,
        "_meta": {SERVER_INFO_META: {"name": "contract-lab", "version": "1.0.0"}},
    }
