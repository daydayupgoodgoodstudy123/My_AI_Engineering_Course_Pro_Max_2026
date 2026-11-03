"""A clock that moves only when told to."""
from __future__ import annotations


class ManualClock:
    """Seconds since the epoch, set by hand. Tests and replays move it; calling it reads it."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now
