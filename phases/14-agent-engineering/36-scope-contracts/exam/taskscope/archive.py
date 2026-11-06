"""Closed scope reports, archived as one JSON file per task under closed/."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .check import ScopeReport
from .contract import RunSummary, ScopeContract


@dataclass
class ClosedTask:
    """Everything the gate knew when it closed a task."""

    contract: ScopeContract  # the effective contract the run was checked against
    run: RunSummary
    report: ScopeReport
    closed_at: float  # seconds since the epoch


class ReportArchive:
    """closed/<task_id>.json under root, one file per closed task.

    Each file holds one strict JSON object (no NaN or Infinity). Its top level carries
    "task_id", "passed" (a JSON boolean, report.passed()) and "closed_at", for auditors
    who read the archive with other tools, plus whatever load needs to rebuild the
    ClosedTask exactly.
    """

    def __init__(self, root: str | Path) -> None:
        self.directory = Path(root) / "closed"

    def close(self, task: ClosedTask) -> Path:
        """Archive a closed task under its report's task_id and return the file's path.

        A task is closed once. The file is created exclusively: an existing entry of any
        kind is never replaced or followed, and closing again raises FileExistsError. A
        record that strict JSON cannot carry raises ValueError and leaves nothing behind.
        A task_id is a plain file name (a letter or digit, then letters, digits, ".", "_"
        or "-"); anything else raises ValueError.
        """
        raise NotImplementedError

    def load(self, task_id: str) -> ClosedTask:
        """The archived task, exactly as it was closed. An unknown task_id raises KeyError."""
        raise NotImplementedError

    def task_ids(self) -> list[str]:
        """The task_ids of every closed task, sorted. Other files in closed/ are skipped."""
        raise NotImplementedError
