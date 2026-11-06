"""Watch a run's event log as it arrives and report surface violations as NDJSON."""
from __future__ import annotations

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
    raise NotImplementedError
