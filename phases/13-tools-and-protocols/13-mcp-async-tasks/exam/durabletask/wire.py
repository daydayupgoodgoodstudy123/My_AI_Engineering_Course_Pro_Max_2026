"""Protocol pieces every handler shares: request _meta, results, errors and timestamps."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"
SUBSCRIPTION_ID_META = "io.modelcontextprotocol/subscriptionId"
TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
SERVER_INFO = {"name": "durabletask", "version": "1.0.0"}
WIRE_TIME = "%Y-%m-%dT%H:%M:%SZ"


class McpError(Exception):
    """A JSON-RPC error: a code, a message and optional data."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(code, message, data)
        self.code = code
        self.message = message
        self.data = data

    def to_error(self) -> dict[str, Any]:
        """The JSON-RPC error object. data appears only when there is some."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = copy.deepcopy(self.data)
        return error


def request_meta(*, tasks: bool = True) -> dict[str, Any]:
    """The _meta a client sends on every request. tasks=False leaves the Tasks extension out."""
    extensions = {TASKS_EXTENSION: {}} if tasks else {}
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CAPABILITIES_META: {"extensions": extensions},
        CLIENT_INFO_META: {"name": "course-client", "version": "1.0.0"},
    }


def make_request(
    request_id: int | str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    tasks: bool = True,
) -> dict[str, Any]:
    """A JSON-RPC request whose params carry this request's own _meta."""
    body = copy.deepcopy(params) if params else {}
    body["_meta"] = request_meta(tasks=tasks)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body}


def server_meta() -> dict[str, Any]:
    """The _meta that identifies this server on a result."""
    return {SERVER_INFO_META: dict(SERVER_INFO)}


def complete(**fields: Any) -> dict[str, Any]:
    """A finished result: resultType "complete", the fields, and this server's identity."""
    return {"resultType": "complete", **fields, "_meta": server_meta()}


def validate_request_meta(params: dict[str, Any]) -> dict[str, Any]:
    """Check the protocol version and capabilities that every request carries; return _meta."""
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise McpError(-32602, "missing request _meta")
    requested = meta.get(PROTOCOL_META)
    if not isinstance(requested, str):
        raise McpError(-32602, "missing protocol version")
    if requested != PROTOCOL_VERSION:
        raise McpError(
            -32022,
            "unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
    if not isinstance(meta.get(CAPABILITIES_META), dict):
        raise McpError(-32602, "missing client capabilities")
    return meta


def require_tasks_extension(meta: dict[str, Any]) -> None:
    """-32021 unless this request declares the Tasks extension."""
    extensions = meta[CAPABILITIES_META].get("extensions")
    if not isinstance(extensions, dict) or not isinstance(extensions.get(TASKS_EXTENSION), dict):
        raise McpError(
            -32021,
            "missing required client capability",
            {"requiredCapabilities": {"extensions": {TASKS_EXTENSION: {}}}},
        )


def format_time(moment: datetime) -> str:
    """A wire timestamp: UTC, whole seconds, Z suffix, e.g. 2026-08-21T10:30:00Z."""
    return moment.astimezone(timezone.utc).strftime(WIRE_TIME)


def parse_time(text: str) -> datetime:
    """Read a wire timestamp back as an aware UTC datetime."""
    return datetime.strptime(text, WIRE_TIME).replace(tzinfo=timezone.utc)
