"""Plan a fan-out before running it: dependencies, a concurrency limit and the wall clock.

Not every turn can run all at once. write_file has to wait for create_file, and a
rate-limited API takes only so many calls at a time. plan_fanout simulates the turn in
integer milliseconds and says when each call would start and end.
"""
from __future__ import annotations

import heapq
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
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")
    by_id: dict[str, PlannedCall] = {}
    for call in calls:
        if call.id in by_id:
            raise ValueError(f"duplicate call id {call.id!r}")
        by_id[call.id] = call
    for call in calls:
        unknown = [dep for dep in call.after if dep not in by_id]
        if unknown:
            raise ValueError(f"{call.id} depends on unknown calls {unknown}")
    _reject_cycles(calls)

    order = {call.id: i for i, call in enumerate(calls)}
    state = {call.id: "waiting" for call in calls}
    start: dict[str, int] = {}
    end: dict[str, int] = {}
    queue: list[str] = []  # ready calls waiting for a slot, first come first served
    running: list[tuple[int, int, str]] = []  # heap of (end_ms, declaration order, id)

    def settle() -> None:
        """Skip what a failure blocks, then queue what just became ready."""
        changed = True
        while changed:
            changed = False
            for call in calls:
                if state[call.id] == "waiting" and any(
                    state[dep] in ("failed", "skipped") for dep in call.after
                ):
                    state[call.id] = "skipped"
                    changed = True
        for call in calls:
            if state[call.id] == "waiting" and all(state[dep] == "ok" for dep in call.after):
                state[call.id] = "queued"
                queue.append(call.id)

    now = 0
    settle()
    while queue or running:
        while queue and len(running) < limit:
            cid = queue.pop(0)
            state[cid] = "running"
            start[cid] = now
            heapq.heappush(running, (now + by_id[cid].latency_ms, order[cid], cid))
        now = running[0][0]
        while running and running[0][0] == now:
            _, _, cid = heapq.heappop(running)
            end[cid] = now
            state[cid] = "failed" if by_id[cid].fails else "ok"
        settle()

    slots = {call.id: Slot(state[call.id], start.get(call.id), end.get(call.id)) for call in calls}
    serial = sum(by_id[cid].latency_ms for cid in start)
    return Plan(slots, max(end.values(), default=0), serial)


def _reject_cycles(calls: list[PlannedCall]) -> None:
    """Raise ValueError if the dependencies form a cycle, whatever the simulation would skip."""
    needs = {call.id: set(call.after) for call in calls}
    free = [cid for cid, deps in needs.items() if not deps]
    while free:
        finished = free.pop()
        for cid, deps in needs.items():
            if finished in deps:
                deps.discard(finished)
                if not deps:
                    free.append(cid)
    stuck = [cid for cid, deps in needs.items() if deps]
    if stuck:
        raise ValueError(f"dependency cycle: {stuck} can never start")
