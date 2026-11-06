"""Closed scope reports, archived as one JSON file per task under closed/."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .check import Finding, ScopeReport
from .contract import RunSummary, ScopeContract

TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


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
        path = self._path(task.report.task_id)
        record = {
            "task_id": task.report.task_id,
            "passed": task.report.passed(),
            "closed_at": task.closed_at,
            "contract": asdict(task.contract),
            "run": asdict(task.run),
            "report": asdict(task.report),
        }
        payload = (json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        self.directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(payload)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path

    def load(self, task_id: str) -> ClosedTask:
        """The archived task, exactly as it was closed. An unknown task_id raises KeyError."""
        path = self._path(task_id)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(task_id) from None
        report = dict(record["report"])
        report["findings"] = [Finding(**finding) for finding in report["findings"]]
        return ClosedTask(
            contract=ScopeContract(**record["contract"]),
            run=RunSummary(**record["run"]),
            report=ScopeReport(**report),
            closed_at=record["closed_at"],
        )

    def task_ids(self) -> list[str]:
        """The task_ids of every closed task, sorted. Other files in closed/ are skipped."""
        if not self.directory.is_dir():
            return []
        return sorted(
            entry.name[: -len(".json")]
            for entry in self.directory.iterdir()
            if entry.name.endswith(".json") and TASK_ID.fullmatch(entry.name[: -len(".json")])
        )

    def _path(self, task_id: str) -> Path:
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise ValueError(f"not a plain task id: {task_id!r}")
        return self.directory / f"{task_id}.json"
