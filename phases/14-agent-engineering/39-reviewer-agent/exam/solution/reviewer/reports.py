"""Review report history on disk.

    root/objects/<sha256>.json   one report body; the SHA-256 of its bytes is its name
    root/index.jsonl             one JSON line per recorded attempt:
                                 {"task": <task_id>, "attempt": <n>, "sha256": <digest>}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .rubric import DimensionScore, ReviewReport


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
        self._objects = self.root / "objects"
        self._index = self.root / "index.jsonl"
        self._objects.mkdir(parents=True, exist_ok=True)
        self._digests: dict[str, list[str]] = {}
        if self._index.exists():
            for line in self._index.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                self._digests.setdefault(entry["task"], []).append(entry["sha256"])

    def record(self, report: ReviewReport, attempt: int) -> str:
        """Record report as attempt `attempt` of its task and return the body's SHA-256 hex digest.

        Every score must be an int from 0 to 2 (a bool or a float is rejected), and attempt must
        be the task's next number or one already recorded; anything else raises ValueError.
        """
        for dim in report.dimensions:
            if type(dim.score) is not int or not 0 <= dim.score <= 2:
                raise ValueError(f"{dim.name}: a score is an int from 0 to 2, got {dim.score!r}")
        body = _body(report)
        digest = hashlib.sha256(body).hexdigest()
        recorded = self._digests.get(report.task_id, [])
        if type(attempt) is int and 1 <= attempt <= len(recorded):
            if recorded[attempt - 1] != digest:
                raise ReportConflict(f"{report.task_id} attempt {attempt} is already recorded with another report")
            return digest
        if type(attempt) is not int or attempt != len(recorded) + 1:
            raise ValueError(f"the next attempt of {report.task_id} is {len(recorded) + 1}, got {attempt!r}")
        obj = self._objects / f"{digest}.json"
        if not obj.exists():
            obj.write_bytes(body)
        with self._index.open("a", encoding="utf-8") as index:
            index.write(json.dumps({"task": report.task_id, "attempt": attempt, "sha256": digest}) + "\n")
        self._digests.setdefault(report.task_id, []).append(digest)
        return digest

    def load(self, task_id: str, attempt: int) -> ReviewReport:
        """The recorded report, equal to the one recorded: the same dimensions in the same order,
        int scores, notes character for character. Unknown attempts raise KeyError."""
        recorded = self._digests.get(task_id, [])
        if type(attempt) is not int or not 1 <= attempt <= len(recorded):
            raise KeyError(f"{task_id} attempt {attempt!r} is not recorded")
        data = json.loads((self._objects / f"{recorded[attempt - 1]}.json").read_bytes())
        dims = [DimensionScore(d["name"], d["score"], d["note"]) for d in data["dimensions"]]
        return ReviewReport(data["task_id"], data["total"], data["verdict"], dims)

    def attempts(self, task_id: str) -> list[int]:
        """The task's recorded attempt numbers, in order (empty for a task never recorded)."""
        return list(range(1, len(self._digests.get(task_id, [])) + 1))


def _body(report: ReviewReport) -> bytes:
    return json.dumps(
        {
            "task_id": report.task_id,
            "total": report.total,
            "verdict": report.verdict,
            "dimensions": [{"name": d.name, "score": d.score, "note": d.note} for d in report.dimensions],
        },
        ensure_ascii=False,
    ).encode("utf-8")
