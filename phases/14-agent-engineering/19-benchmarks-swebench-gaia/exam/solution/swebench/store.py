"""The results of one benchmark run, in two CSV files: one row per task, one row per test outcome."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .harness import PHASES, STATUSES, Outcome

RUN_FIELDS = ["instance_id", "status", "tokens", "wall_ms", "steps", "patch"]
TEST_FIELDS = ["instance_id", "test_id", "phase", "passed"]


@dataclass
class TaskRecord:
    instance_id: str
    status: str
    patch: str
    tokens: int
    wall_ms: int
    steps: int
    outcomes: list[Outcome] = field(default_factory=list)


class ResultStore:
    """Every task record of one run, in a directory holding runs.csv and tests.csv.

    runs.csv has one row per task: instance_id,status,tokens,wall_ms,steps,patch.
    tests.csv has one row per test outcome: instance_id,test_id,phase,passed, with passed
    written as 1 or 0. Each file starts with its header line, once. The patch is the agent's
    diff and comes back byte for byte. Records are durable as soon as add() returns.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._runs = self.root / "runs.csv"
        self._tests = self.root / "tests.csv"
        for path, header in ((self._runs, RUN_FIELDS), (self._tests, TEST_FIELDS)):
            if not path.exists():
                with path.open("w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(header)
        self._ids = {row["instance_id"] for row in self._read(self._runs)}

    def add(self, record: TaskRecord) -> None:
        """Append one task record. A bad status or phase, a cost that is not a non-negative int,
        or an instance id already in the run raises ValueError, and nothing is written."""
        if record.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {record.status!r}")
        for name in ("tokens", "wall_ms", "steps"):
            value = getattr(record, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        for outcome in record.outcomes:
            if outcome.phase not in PHASES:
                raise ValueError(f"phase must be one of {PHASES}, got {outcome.phase!r}")
        if record.instance_id in self._ids:
            raise ValueError(f"{record.instance_id!r} is already in this run")
        with self._tests.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for o in record.outcomes:
                writer.writerow([record.instance_id, o.test_id, o.phase, 1 if o.passed else 0])
        with self._runs.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [record.instance_id, record.status, record.tokens, record.wall_ms, record.steps, record.patch]
            )
        self._ids.add(record.instance_id)

    def get(self, instance_id: str) -> TaskRecord:
        """One stored record. An unknown instance id raises KeyError."""
        for record in self.records():
            if record.instance_id == instance_id:
                return record
        raise KeyError(instance_id)

    def records(self) -> list[TaskRecord]:
        """Every stored record in the order it was added, outcomes in their original order."""
        outcomes: dict[str, list[Outcome]] = {}
        for row in self._read(self._tests):
            outcomes.setdefault(row["instance_id"], []).append(
                Outcome(row["test_id"], row["phase"], row["passed"] == "1")
            )
        return [
            TaskRecord(
                row["instance_id"],
                row["status"],
                row["patch"],
                int(row["tokens"]),
                int(row["wall_ms"]),
                int(row["steps"]),
                outcomes.get(row["instance_id"], []),
            )
            for row in self._read(self._runs)
        ]

    @staticmethod
    def _read(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
