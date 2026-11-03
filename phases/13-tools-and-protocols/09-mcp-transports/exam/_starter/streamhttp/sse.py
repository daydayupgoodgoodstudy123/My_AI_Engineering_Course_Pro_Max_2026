"""Request-scoped SSE: one long tools/call answered as a text/event-stream response."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import Any, Union

from .protocol import complete

SSE_HEADERS = (
    ("Content-Type", "text/event-stream"),
    ("Cache-Control", "no-cache"),
    ("X-Accel-Buffering", "no"),
)


@dataclass(frozen=True)
class Progress:
    """The tool got further: progress so far, and the total and a short message when it has them."""

    progress: int | float
    total: int | float | None = None
    message: str | None = None


@dataclass(frozen=True)
class Heartbeat:
    """The tool is still working but has nothing new to report."""


@dataclass(frozen=True)
class ToolResult:
    """The tool's final answer."""

    content: list[dict[str, Any]]
    is_error: bool = False


Step = Union[Progress, Heartbeat, ToolResult]


async def stream_tool_call(
    request_id: int | str,
    steps: AsyncGenerator[Step, None],
    *,
    progress_token: int | str | None = None,
) -> AsyncIterator[bytes]:
    """Answer one tools/call as a request-scoped SSE stream, in UTF-8 bytes.

    Each message is one event: a single "data: " line of compact JSON, then a blank line. Lines
    end with "\\n".
    - Progress becomes a notifications/progress whose params are progressToken, progress, and
      total and message when the step has them. A progress_token of None means the client asked
      for no progress, and none is sent.
    - Heartbeat becomes the comment line ":" and a blank line. It keeps proxies from closing a
      quiet connection, and it is not progress.
    - ToolResult becomes the final JSON-RPC response to request_id. The stream ends with it, and
      steps is not read any further.

    Each event is written as soon as its step arrives. No event carries an id: a modern stream is
    never resumed. Closing the stream early cancels the call: steps is closed before the close
    returns.
    """
    raise NotImplementedError
