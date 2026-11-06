"""Labeled traces on disk, one JSON file per trace, plus the last-known-good baseline."""
from __future__ import annotations

from .trace import Trace, TraceStep


class TraceStore:
    """A directory of labeled traces.

    Layout under root: traces/ holds one JSON file per trace, and BASELINE holds the trace
    ids of the last-known-good set. Trace ids come from the agent runtime: any string is
    allowed, including "/", and ids that differ only in case are different traces.
    """

    def __init__(self, root: str) -> None:
        raise NotImplementedError

    def put(self, trace: Trace, labels: list[str]) -> None:
        """Store a trace with its labels, replacing any earlier copy with the same tid."""
        raise NotImplementedError

    def get(self, tid: str) -> tuple[Trace, list[str]]:
        """The stored trace and its labels, exactly as put. Unknown ids raise KeyError."""
        raise NotImplementedError

    def tids(self) -> list[str]:
        """Every stored trace id, once each, sorted."""
        raise NotImplementedError

    def set_baseline(self, tids: list[str]) -> None:
        """Make these stored traces the last-known-good set, in the given order.

        Ids that are not stored raise ValueError. The update is atomic: a reader sees the
        old baseline or the new one, never a mix, and a failed update leaves the old
        baseline and no stray files behind.
        """
        raise NotImplementedError

    def baseline(self) -> list[str] | None:
        """The last-known-good trace ids, or None before any baseline is set."""
        raise NotImplementedError
