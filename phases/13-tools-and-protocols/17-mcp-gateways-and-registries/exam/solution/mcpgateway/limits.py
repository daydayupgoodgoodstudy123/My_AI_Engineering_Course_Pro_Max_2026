"""Rate limits without sessions: one sliding window per caller, tool and cost class."""
from __future__ import annotations

from collections import deque
from typing import NamedTuple


class LimitKey(NamedTuple):
    """Who is calling what: the principal at its issuer, the resource its token is for,
    the public tool, and the tool's cost class ("read" or "write")."""

    principal: str
    issuer: str
    resource: str
    tool: str
    cost_class: str


class RateLimiter:
    """Sliding-window rate limits, one window per key.

    A key may make at most `limits[key.cost_class]` allowed calls in any `window_s`
    seconds: a call allowed at time t stops counting at t + window_s. Refused calls do
    not count. `now` comes from the caller's clock and never goes backwards.
    """

    def __init__(self, limits: dict[str, int], window_s: float) -> None:
        self.limits = dict(limits)
        self.window_s = window_s
        self._calls: dict[LimitKey, deque[float]] = {}

    def allow(self, key: LimitKey, now: float) -> bool:
        """Count one call for `key` at `now` if the window has room; say whether it was allowed."""
        calls = self._calls.setdefault(key, deque())
        while calls and calls[0] <= now - self.window_s:
            calls.popleft()
        if len(calls) >= self.limits[key.cost_class]:
            return False
        calls.append(now)
        return True
