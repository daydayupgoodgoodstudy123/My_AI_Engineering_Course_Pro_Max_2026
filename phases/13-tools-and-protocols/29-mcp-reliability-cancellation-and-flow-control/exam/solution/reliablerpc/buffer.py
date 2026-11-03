"""A bounded outbound queue for one stream: progress may be lost, responses may not."""
from __future__ import annotations

from collections import deque
from typing import Any

from .wire import ReliabilityError, is_progress


class StreamClosed(ReliabilityError):
    """The stream is gone: nothing more can be written to it."""


class BoundedSseBuffer:
    """Messages waiting for a slow consumer, never more than capacity of them.

    Progress is replaceable, the final response to a request is not:
    1. a progress notification for the same token as the newest queued message replaces it;
    2. when the queue is full, the oldest queued progress notification makes room;
    3. every progress notification lost either way is counted in dropped_progress and sets
       needs_refetch, so the consumer knows to read the authoritative state again;
    4. a response is never dropped. When the queue is full of responses, a new progress
       notification is lost, and a new response raises ReliabilityError and changes nothing.

    Every push takes constant time, however many responses are queued ahead of it.
    Once closed, the buffer refuses every write with StreamClosed.
    """

    def __init__(self, capacity: int) -> None:
        if type(capacity) is not int or capacity < 2:
            raise ReliabilityError("SSE buffer capacity must be an integer of at least two")
        self.capacity = capacity
        self.dropped_progress = 0
        self.needs_refetch = False
        self.closed = False
        self._messages: dict[int, dict[str, Any]] = {}  # insertion-ordered by sequence number
        self._progress: deque[int] = deque()  # sequence numbers of queued progress, oldest first
        self._next = 0

    def __len__(self) -> int:
        return len(self._messages)

    def push_progress(self, notification: dict[str, Any]) -> None:
        self._check_open()
        token = notification["params"]["progressToken"]
        if self._messages:
            newest = next(reversed(self._messages))
            queued = self._messages[newest]
            if is_progress(queued) and queued["params"]["progressToken"] == token:
                self._messages[newest] = notification
                self._lose_progress()
                return
        if len(self._messages) >= self.capacity and not self._drop_oldest_progress():
            self._lose_progress()
            return
        self._append(notification, progress=True)

    def push_final(self, message: dict[str, Any]) -> None:
        self._check_open()
        if len(self._messages) >= self.capacity and not self._drop_oldest_progress():
            raise ReliabilityError("buffer cannot discard a final response")
        self._append(message, progress=False)

    def drain(self) -> list[dict[str, Any]]:
        """Every queued message, oldest first; the queue is empty afterwards."""
        drained = list(self._messages.values())
        self._messages.clear()
        self._progress.clear()
        return drained

    def close(self) -> None:
        self.closed = True

    def _append(self, message: dict[str, Any], *, progress: bool) -> None:
        self._messages[self._next] = message
        if progress:
            self._progress.append(self._next)
        self._next += 1

    def _drop_oldest_progress(self) -> bool:
        if not self._progress:
            return False
        del self._messages[self._progress.popleft()]
        self._lose_progress()
        return True

    def _lose_progress(self) -> None:
        self.dropped_progress += 1
        self.needs_refetch = True

    def _check_open(self) -> None:
        if self.closed:
            raise StreamClosed("write to a closed response stream")
