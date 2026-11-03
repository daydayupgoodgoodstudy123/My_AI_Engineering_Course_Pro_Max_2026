"""JSON-RPC and MCP wire helpers shared by the client, the era probe and the stdio pool."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
# HeaderMismatch, MissingRequiredClientCapability, UnsupportedProtocolVersion
RECOGNIZED_MODERN_ERRORS = frozenset({-32020, -32021, -32022})
CLIENT_INFO = {"name": "multipeer", "version": "1.0.0"}


class ProtocolError(RuntimeError):
    """A peer answered something the protocol does not allow, or no era could be agreed on."""


@dataclass(frozen=True)
class Selection:
    """The era chosen for one transport peer.

    This is client bookkeeping, not protocol session state. It lasts as long as the transport:
    a restarted process or a changed endpoint is negotiated again.
    """

    era: str  # "modern" or "legacy"
    protocol_version: str
    capabilities: dict
    server_info: dict


def modern_request(
    request_id: int | str,
    method: str,
    params: dict | None,
    version: str,
    capabilities: dict,
) -> dict:
    """A modern request, stamped from scratch: every one carries its own _meta."""
    body = dict(params or {})
    body["_meta"] = {
        VERSION_KEY: version,
        CAPABILITIES_KEY: dict(capabilities),
        CLIENT_INFO_KEY: dict(CLIENT_INFO),
    }
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body}


def legacy_request(request_id: int | str, method: str, params: dict | None = None) -> dict:
    """A request in the legacy shape: no modern _meta."""
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": dict(params or {})}


def notification(method: str, params: dict | None = None) -> dict:
    """A notification has no id, and nothing answers it."""
    return {"jsonrpc": "2.0", "method": method, "params": dict(params or {})}


def valid_id(value: Any) -> bool:
    """Request ids are strings or integers. A bool is not an integer here, and neither is 1.0."""
    return type(value) in (int, str)


def same_id(a: Any, b: Any) -> bool:
    """JSON-RPC ids match when both the type and the value match: true is not 1, and "1" is not 1."""
    return valid_id(a) and type(a) is type(b) and a == b


def decode_response(response: Any) -> tuple[str, dict]:
    """Check a response envelope and return ("result", result) or ("error", error).

    The caller matches the id; this checks everything else.
    """
    if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
        raise ProtocolError("not a JSON-RPC 2.0 response")
    has_result, has_error = "result" in response, "error" in response
    if has_result == has_error:
        raise ProtocolError("a response carries exactly one of result or error")
    if has_result:
        if not isinstance(response["result"], dict):
            raise ProtocolError("a result must be an object")
        return "result", response["result"]
    error = response["error"]
    if (
        not isinstance(error, dict)
        or type(error.get("code")) is not int
        or not isinstance(error.get("message"), str)
    ):
        raise ProtocolError("an error needs an integer code and a string message")
    return "error", error


def mutual_version(advertised: Sequence[Any], supported: Sequence[str]) -> str | None:
    """The highest version on both lists, or None when they share none.

    Versions are dates (YYYY-MM-DD), so the highest is the latest.
    """
    for version in advertised:
        if isinstance(version, str) and version in supported:
            return version
    return None


def modern_selection(result: dict, supported: Sequence[str]) -> Selection:
    """Read a DiscoverResult: the peer is modern, at the highest version both sides support."""
    if result.get("resultType") != "complete":
        raise ProtocolError("a DiscoverResult has resultType complete")
    advertised = result.get("supportedVersions")
    if not isinstance(advertised, list) or not all(isinstance(v, str) for v in advertised):
        raise ProtocolError("supportedVersions must be a list of strings")
    version = mutual_version(advertised, supported)
    if version is None:
        raise ProtocolError("no mutually supported modern version")
    capabilities = result.get("capabilities", {})
    meta = result.get("_meta", {})
    server_info = meta.get(SERVER_INFO_KEY, {}) if isinstance(meta, dict) else {}
    if not isinstance(capabilities, dict) or not isinstance(server_info, dict):
        raise ProtocolError("malformed DiscoverResult")
    return Selection("modern", version, capabilities, server_info)
