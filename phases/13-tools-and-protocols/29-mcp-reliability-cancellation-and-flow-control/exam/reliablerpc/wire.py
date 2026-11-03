"""Transport names, request states and the JSON-RPC messages every part of reliablerpc sends."""
from __future__ import annotations

from typing import Any

STDIO = "stdio"
STREAMABLE_HTTP = "streamable_http"

IN_PROGRESS = "in_progress"
COMPLETED = "completed"
CANCELLED = "cancelled"


class ReliabilityError(ValueError):
    """Raised when a reliability invariant would be broken."""


def notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """A JSON-RPC notification: no id, and nobody answers it."""
    return {"jsonrpc": "2.0", "method": method, "params": params}


def response(request_id: int | str, result: dict[str, Any]) -> dict[str, Any]:
    """The final JSON-RPC response to request_id."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def progress_notification(
    token: int | str,
    progress: int | float,
    total: int | float | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """notifications/progress for one progress token; total and message only when given."""
    params: dict[str, Any] = {"progressToken": token, "progress": progress}
    if total is not None:
        params["total"] = total
    if message is not None:
        params["message"] = message
    return notification("notifications/progress", params)


def is_progress(message: dict[str, Any]) -> bool:
    return message.get("method") == "notifications/progress"
