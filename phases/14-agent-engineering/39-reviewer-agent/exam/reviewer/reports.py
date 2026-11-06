"""Review report history on disk.

    root/objects/<sha256>.json   one report body; the SHA-256 of its bytes is its name
    root/index.jsonl             one JSON line per recorded attempt:
                                 {"task": <task_id>, "attempt": <n>, "sha256": <digest>}
"""
from __future__ import annotations

from pathlib import Path

from .rubric import ReviewReport


class ReportConflict(Exception):
    """An attempt that is already recorded was recorded again with a different report."""


class ReportStore:
    """The append-only history of a project's review reports.

    Every review of a task is one attempt; a task's attempts are numbered 1, 2, 3, ... with no
    gaps. A recorded attempt never changes: recording it again with an equal report returns the
    same digest and writes nothing, and recording it with a different report raises
    ReportConflict. The attempt number lives in the index, not in the body, so two attempts
    with equal reports share one object. A rejected record writes nothing. A store opened on
    the same root later sees everything recorded before.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        # TODO: create the layout and read the index

    def record(self, report: ReviewReport, attempt: int) -> str:
        """Record report as attempt `attempt` of its task and return the body's SHA-256 hex digest.

        Every score must be an int from 0 to 2 (a bool or a float is rejected), and attempt must
        be the task's next number or one already recorded; anything else raises ValueError.
        """
        raise NotImplementedError

    def load(self, task_id: str, attempt: int) -> ReviewReport:
        """The recorded report, equal to the one recorded: the same dimensions in the same order,
        int scores, notes character for character. Unknown attempts raise KeyError."""
        raise NotImplementedError

    def attempts(self, task_id: str) -> list[int]:
        """The task's recorded attempt numbers, in order (empty for a task never recorded)."""
        raise NotImplementedError
