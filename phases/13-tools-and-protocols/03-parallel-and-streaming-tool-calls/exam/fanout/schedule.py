"""Plan a fan-out before running it: dependencies, a concurrency limit and the wall clock.

Not every turn can run all at once. write_file has to wait for create_file, and a
rate-limited API takes only so many calls at a time. plan_fanout simulates the turn in
integer milliseconds and says when each call would start and end.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedCall:
    id: str
    latency_ms: int  # a positive integer
    after: tuple[str, ...] = ()  # ids of the calls this one needs first
    fails: bool = False  # the call runs for its latency, then fails


@dataclass(frozen=True)
class Slot:
    status: str  # "ok", "failed" or "skipped"
    start_ms: int | None = None  # None for a skipped call
    end_ms: int | None = None


@dataclass(frozen=True)
class Plan:
    slots: dict[str, Slot]  # by call id, in declaration order
    wall_ms: int  # when the last call ends
    serial_ms: int  # the same calls run one after another


def plan_fanout(calls: list[PlannedCall], limit: int) -> Plan:
    """Simulate a turn with at most `limit` calls running at once.

    A call is ready once every call in its `after` has finished ok; then it waits for a free
    slot. Waiting calls start first come, first served, and calls that become ready at the
    same moment queue in declaration order. A slot freed at t is taken again at t. When a call
    fails, every call that depends on it, directly or through other calls, is skipped: it never
    runs and takes no slot. serial_ms adds up the latencies of the calls that run.

    Raises ValueError for a limit below 1, a duplicate id, an unknown dependency or a cycle.
    """
    raise NotImplementedError
