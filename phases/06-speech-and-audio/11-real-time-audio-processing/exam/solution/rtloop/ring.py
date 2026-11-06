"""A fixed-size ring buffer between the audio callback and the processing loop."""
from __future__ import annotations

from collections.abc import Sequence


class RingBuffer:
    """Fixed-capacity FIFO of samples. The audio callback writes, the processing loop reads.

    The storage is allocated once and reused. When a write does not fit, the oldest samples
    are overwritten: a real-time loop keeps the newest audio, and `dropped` counts every
    sample lost that way.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._buf: list[float | None] = [None] * capacity
        self._written = 0  # samples written since the stream started
        self._read = 0  # samples read or dropped since the stream started
        self.dropped = 0

    @property
    def position(self) -> int:
        """Stream index of the oldest sample still held."""
        return self._read

    def level(self) -> int:
        """Samples held and not read yet."""
        return self._written - self._read

    def write(self, samples: Sequence[float]) -> None:
        """Append samples, overwriting the oldest ones when they do not fit."""
        n = len(samples)
        overflow = self.level() + n - self.capacity
        if overflow > 0:
            self._read += overflow
            self.dropped += overflow
        if n > self.capacity:
            samples = samples[n - self.capacity :]
            self._written += n - self.capacity
            n = self.capacity
        start = self._written % self.capacity
        first = min(n, self.capacity - start)
        self._buf[start : start + first] = samples[:first]
        self._buf[: n - first] = samples[first:]
        self._written += n

    def read(self, n: int) -> list[float]:
        """Remove and return up to n of the oldest samples."""
        n = max(0, min(n, self.level()))
        start = self._read % self.capacity
        first = min(n, self.capacity - start)
        out = self._buf[start : start + first] + self._buf[: n - first]
        self._read += n
        return out
