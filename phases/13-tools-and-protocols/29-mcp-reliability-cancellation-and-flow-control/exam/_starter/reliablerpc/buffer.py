"""A bounded outbound queue for one stream: progress may be lost, responses may not."""
from __future__ import annotations

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
        self._messages: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._messages)

    def push_progress(self, notification: dict[str, Any]) -> None:
        self._check_open()
        token = notification["params"]["progressToken"]
        if self._messages:
            queued = self._messages[-1]
            if is_progress(queued) and queued["params"]["progressToken"] == token:
                self._messages[-1] = notification
                self._lose_progress()
                return
        if len(self._messages) >= self.capacity and not self._drop_oldest_progress():
            self._lose_progress()
            return
        self._messages.append(notification)

    def push_final(self, message: dict[str, Any]) -> None:
        self._check_open()
        if len(self._messages) >= self.capacity and not self._drop_oldest_progress():
            raise ReliabilityError("buffer cannot discard a final response")
        self._messages.append(message)

    def drain(self) -> list[dict[str, Any]]:
        """Every queued message, oldest first; the queue is empty afterwards."""
        drained = list(self._messages)
        self._messages.clear()
        return drained

    def close(self) -> None:
        self.closed = True

    def _drop_oldest_progress(self) -> bool:
        for index, message in enumerate(self._messages):
            if is_progress(message):
                del self._messages[index]
                self._lose_progress()
                return True
        return False

    def _lose_progress(self) -> None:
        self.dropped_progress += 1
        self.needs_refetch = True

    def _check_open(self) -> None:
        if self.closed:
            raise StreamClosed("write to a closed response stream")
