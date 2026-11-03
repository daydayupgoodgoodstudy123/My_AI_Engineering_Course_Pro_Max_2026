"""One tools/call answered as an SSE response on Streamable HTTP, under two clocks."""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Union

from .wire import progress_notification, response


@dataclass(frozen=True)
class Budget:
    """idle_timeout_ms: longest time without progress. max_timeout_ms: longest time in all.

    keepalive_ms: longest time the stream may stay silent.
    """

    idle_timeout_ms: int
    max_timeout_ms: int
    keepalive_ms: int


@dataclass(frozen=True)
class Progress:
    progress: int | float
    total: int | float | None = None
    message: str | None = None


@dataclass(frozen=True)
class Done:
    result: dict[str, Any]


Event = Union[Progress, Done]


class SimClock:
    """Simulated milliseconds. advance_to(t) stands in for waiting until t; time never goes back."""

    def __init__(self, now_ms: int = 0) -> None:
        self.now_ms = now_ms

    def advance_to(self, at_ms: int) -> None:
        if at_ms < self.now_ms:
            raise ValueError(f"the clock is at {self.now_ms} ms and cannot go back to {at_ms} ms")
        self.now_ms = at_ms


class CallStream:
    """The SSE response to one tools/call, written while its worker runs.

    The worker yields (at_ms, event) pairs in time order: Progress reports, then Done with the
    tool's result. A worker that runs out of events before Done has stalled. The request starts
    at the clock's time when the stream is created. Iterating writes the response as bytes, one
    chunk per SSE message, each as soon as it is due, moving the clock to the time it is written:

    - Progress becomes a notifications/progress data event, but only when the request has a
      progress token and the value is greater than the last one sent. Anything else is not
      progress: it is not sent and does not restart the idle clock.
    - Done becomes the final JSON-RPC response, and the stream ends there.
    - When keepalive_ms pass with nothing written, a keepalive is written: the SSE comment line
      ":". A keepalive keeps proxies from closing the connection; it is not progress.
    - Two clocks: the request is cancelled idle_timeout_ms after the last progress sent (or the
      start), or max_timeout_ms after the start, whichever comes first. The stream moves the clock
      to that moment and ends: nothing due then or later is written, and outcome says which
      clock ran out.

    Each data event is "data: " and the message's JSON on one line, then a blank line.
    Whenever the stream ends, completed, cancelled, or closed by the client, the worker is closed.
    """

    def __init__(
        self,
        request_id: int | str,
        worker: Iterator[tuple[int, Event]],
        *,
        clock: SimClock,
        budget: Budget,
        progress_token: int | str | None = None,
    ) -> None:
        self.request_id = request_id
        self.worker = worker
        self.clock = clock
        self.budget = budget
        self.progress_token = progress_token
        self.started_at_ms = clock.now_ms
        self.outcome: str | None = None  # "completed", "idle timeout" or "maximum timeout"

    def headers(self) -> dict[str, str]:
        """Response headers for an SSE stream that proxies deliver as it is written."""
        return {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

    def __iter__(self) -> Iterator[bytes]:
        budget = self.budget
        hard_deadline = self.started_at_ms + budget.max_timeout_ms
        last_progress_at = last_write_at = self.started_at_ms
        last_value: int | float | None = None
        try:
            while True:
                at_ms, event = next(self.worker, (None, None))  # None: the worker has stalled
                while True:
                    deadline = min(hard_deadline, last_progress_at + budget.idle_timeout_ms)
                    keepalive_at = last_write_at + budget.keepalive_ms
                    if deadline <= keepalive_at and (at_ms is None or deadline <= at_ms):
                        self.clock.advance_to(deadline)
                        self.outcome = "maximum timeout" if deadline == hard_deadline else "idle timeout"
                        return
                    if at_ms is not None and at_ms <= keepalive_at:
                        break
                    self.clock.advance_to(keepalive_at)
                    last_write_at = keepalive_at
                    yield b":\n\n"
                self.clock.advance_to(at_ms)
                if isinstance(event, Done):
                    self.outcome = "completed"
                    yield _data(response(self.request_id, event.result))
                    return
                if self.progress_token is None or (last_value is not None and event.progress <= last_value):
                    continue
                last_value = event.progress
                last_progress_at = last_write_at = at_ms
                yield _data(progress_notification(self.progress_token, event.progress, event.total, event.message))
        finally:
            close = getattr(self.worker, "close", None)
            if close is not None:
                close()


def _data(message: dict[str, Any]) -> bytes:
    return b"data: " + json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n\n"
