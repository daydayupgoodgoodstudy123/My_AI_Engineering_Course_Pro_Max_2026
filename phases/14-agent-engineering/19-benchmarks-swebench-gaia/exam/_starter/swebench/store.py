"""The results of one benchmark run, in two CSV files: one row per task, one row per test outcome."""
from __future__ import annotations

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
        # TODO: set up the two files

    def add(self, record: TaskRecord) -> None:
        """Append one task record. A bad status or phase, a cost that is not a non-negative int,
        or an instance id already in the run raises ValueError, and nothing is written."""
        raise NotImplementedError

    def get(self, instance_id: str) -> TaskRecord:
        """One stored record. An unknown instance id raises KeyError."""
        raise NotImplementedError

    def records(self) -> list[TaskRecord]:
        """Every stored record in the order it was added, outcomes in their original order."""
        raise NotImplementedError
