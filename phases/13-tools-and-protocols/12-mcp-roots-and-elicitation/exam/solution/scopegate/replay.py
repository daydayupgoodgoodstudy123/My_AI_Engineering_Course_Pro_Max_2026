"""One-time confirmation nonces for every server object in one process."""
from __future__ import annotations

import heapq
import threading
import time
from collections.abc import Callable
from typing import Any

from .protocol import McpError


class ReplayStore:
    """Consumed nonces, each kept until the state that carried it expires.

    A signed requestState stays valid until it expires, so HMAC alone cannot stop a
    confirmation from being used twice. The store holds at most max_entries live
    nonces. When it is full it refuses new claims, because forgetting a live nonce
    would let its confirmation run again.
    """

    def __init__(self, *, max_entries: int = 1_000, clock: Callable[[], float] = time.time) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self.max_entries = max_entries
        self._clock = clock
        self._consumed: dict[str, float] = {}
        self._expiries: list[tuple[float, str]] = []  # min-heap of (expires_at, nonce)
        self._lock = threading.Lock()

    def claim_and_consume(
        self,
        nonce: str,
        *,
        expires_at: float,
        operation: Callable[[], Any],
    ) -> Any:
        """Run operation and consume nonce, as one atomic step.

        Raises McpError(-32602, "requestState expired") when expires_at <= clock(),
        McpError(-32602, "requestState was already consumed") for a nonce that is still
        held, and McpError(-32023, "replay protection capacity exhausted") when the store
        is full of live nonces. If operation raises, the nonce is not consumed.
        """
        with self._lock:
            now = self._clock()
            while self._expiries and self._expiries[0][0] <= now:
                expiry, old = heapq.heappop(self._expiries)
                if self._consumed.get(old) == expiry:
                    del self._consumed[old]
            if expires_at <= now:
                raise McpError(-32602, "requestState expired")
            if nonce in self._consumed:
                raise McpError(-32602, "requestState was already consumed")
            if len(self._consumed) >= self.max_entries:
                raise McpError(-32023, "replay protection capacity exhausted")
            result = operation()
            self._consumed[nonce] = expires_at
            heapq.heappush(self._expiries, (expires_at, nonce))
            return result
