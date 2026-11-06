"""Every measured run's five outcomes, kept in SQLite."""
from __future__ import annotations

import json
import sqlite3

from .artifacts import PIPELINES
from .outcomes import HANDOFF_LEVELS, OUTCOMES, Outcome

SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    pipeline TEXT NOT NULL,
    outcome TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE (run_id, pipeline, outcome)
)
"""


class OutcomeStore:
    """The outcomes of every measured run, one row per outcome: (run, pipeline, outcome, value).

    A run id names one repetition of the task, and holds at most one outcome per pipeline.
    Every repetition is kept.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def record(self, run_id: str, pipeline: str, outcome: Outcome) -> None:
        """Store one pipeline's outcome for one run.

        Raises ValueError, and stores nothing, when pipeline is not one of PIPELINES or the
        outcome is not what Outcome describes: both flags bool, files_outside_scope a list of
        str, handoff_quality one of HANDOFF_LEVELS, reviewer_total an int from 0 to 10.
        """
        if pipeline not in PIPELINES:
            raise ValueError(f"pipeline must be one of {PIPELINES}, got {pipeline!r}")
        _check(outcome)
        if self._db.execute(
            "SELECT 1 FROM outcomes WHERE run_id = ? AND pipeline = ? LIMIT 1", (run_id, pipeline)
        ).fetchone():
            raise ValueError(f"run {run_id!r} already has a {pipeline} outcome")
        rows = [(run_id, pipeline, name, json.dumps(getattr(outcome, name))) for name in OUTCOMES]
        with self._db:
            self._db.executemany(
                "INSERT INTO outcomes (run_id, pipeline, outcome, value) VALUES (?, ?, ?, ?)", rows
            )

    def get(self, run_id: str, pipeline: str) -> Outcome:
        """The stored outcome, exactly as recorded. An unknown run or pipeline raises KeyError."""
        values = dict(
            self._db.execute(
                "SELECT outcome, value FROM outcomes WHERE run_id = ? AND pipeline = ?",
                (run_id, pipeline),
            )
        )
        if not values:
            raise KeyError((run_id, pipeline))
        return Outcome(**{name: json.loads(values[name]) for name in OUTCOMES})

    def runs(self) -> list[str]:
        """Run ids, in the order they were first recorded."""
        rows = self._db.execute("SELECT run_id FROM outcomes GROUP BY run_id ORDER BY MIN(seq)")
        return [run_id for (run_id,) in rows]

    def outcomes(self) -> list[tuple[str, str, Outcome]]:
        """(run_id, pipeline, outcome) for everything stored, in the order it was recorded."""
        keys = self._db.execute(
            "SELECT run_id, pipeline FROM outcomes GROUP BY run_id, pipeline ORDER BY MIN(seq)"
        ).fetchall()
        return [(run_id, pipeline, self.get(run_id, pipeline)) for run_id, pipeline in keys]

    def close(self) -> None:
        self._db.close()


def _check(outcome: Outcome) -> None:
    for name in ("tests_actually_run", "acceptance_met"):
        if not isinstance(getattr(outcome, name), bool):
            raise ValueError(f"{name} must be a bool")
    files = outcome.files_outside_scope
    if not isinstance(files, list) or not all(isinstance(path, str) for path in files):
        raise ValueError("files_outside_scope must be a list of paths")
    if outcome.handoff_quality not in HANDOFF_LEVELS:
        raise ValueError(f"handoff_quality must be one of {HANDOFF_LEVELS}")
    total = outcome.reviewer_total
    if isinstance(total, bool) or not isinstance(total, int) or not 0 <= total <= 10:
        raise ValueError("reviewer_total must be an int from 0 to 10")
