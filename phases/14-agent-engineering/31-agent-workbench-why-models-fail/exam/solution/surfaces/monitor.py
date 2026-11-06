"""Watch a run's event log as it arrives and report surface violations as NDJSON."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from .report import RepoTask

KINDS = ("write", "run", "claim", "handoff", "end")


@dataclass(frozen=True)
class Event:
    """One record of a run's event log.

    seq numbers the log from 1. A write carries the path written; a run carries the exit
    code the runner captured, or None when it captured none; a claim is the agent declaring
    success; a handoff is the handoff written; end closes the session.
    """

    seq: int
    kind: str
    path: str = ""
    exit_code: int | None = None


async def monitor(events: AsyncIterator[Event], task: RepoTask) -> AsyncIterator[str]:
    """Report surface violations while a run's events arrive, one JSON object per line.

    The log comes through an at-least-once queue: events can arrive out of order, and the
    same event (same seq) can arrive more than once. Check the events in seq order, each seq
    once, and yield a violation as soon as the event that causes it is checked:

      {"seq": n, "surface": "scope", "path": p}           a write outside task.allowed_files,
                                                          once per path
      {"seq": n, "surface": "feedback", "exit_code": c}  a claim whose latest earlier run did
                                                          not exit 0; c is that run's exit
                                                          code, null when it has none or
                                                          when no run came before
      {"seq": n, "surface": "handoff"}                   the end event, when no handoff came
                                                          before it

    If the stream stops while seqs are still missing, raise ValueError naming them.
    """
    checks = _Checks(set(task.allowed_files))
    waiting: dict[int, Event] = {}
    next_seq = 1
    async for event in events:
        if event.seq < next_seq or event.seq in waiting:
            continue  # a redelivery
        waiting[event.seq] = event
        while next_seq in waiting:
            for violation in checks(waiting.pop(next_seq)):
                yield json.dumps(violation) + "\n"
            next_seq += 1
    if waiting:
        missing = [seq for seq in range(next_seq, max(waiting)) if seq not in waiting]
        raise ValueError(f"the log stopped with seqs missing: {missing}")


class _Checks:
    """The per-surface checks, fed one event at a time in seq order."""

    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed
        self.reported: set[str] = set()
        self.last_run: Event | None = None
        self.handoff = False

    def __call__(self, event: Event) -> list[dict]:
        if event.kind not in KINDS:
            raise ValueError(f"unknown event kind {event.kind!r}")
        if event.kind == "write":
            if event.path not in self.allowed and event.path not in self.reported:
                self.reported.add(event.path)
                return [{"seq": event.seq, "surface": "scope", "path": event.path}]
        elif event.kind == "run":
            self.last_run = event
        elif event.kind == "claim":
            code = None if self.last_run is None else self.last_run.exit_code
            if code != 0:
                return [{"seq": event.seq, "surface": "feedback", "exit_code": code}]
        elif event.kind == "handoff":
            self.handoff = True
        elif event.kind == "end":
            if not self.handoff:
                return [{"seq": event.seq, "surface": "handoff"}]
        return []
