"""Every measured run's five outcomes, kept in SQLite."""
from __future__ import annotations

import sqlite3

from .artifacts import PIPELINES
from .outcomes import HANDOFF_LEVELS, OUTCOMES, Outcome


class OutcomeStore:
    """The outcomes of every measured run, one row per outcome: (run, pipeline, outcome, value).

    A run id names one repetition of the task, and holds at most one outcome per pipeline.
    Every repetition is kept.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def record(self, run_id: str, pipeline: str, outcome: Outcome) -> None:
        """Store one pipeline's outcome for one run.

        Raises ValueError, and stores nothing, when pipeline is not one of PIPELINES or the
        outcome is not what Outcome describes: both flags bool, files_outside_scope a list of
        str, handoff_quality one of HANDOFF_LEVELS, reviewer_total an int from 0 to 10.
        """
        raise NotImplementedError

    def get(self, run_id: str, pipeline: str) -> Outcome:
        """The stored outcome, exactly as recorded. An unknown run or pipeline raises KeyError."""
        raise NotImplementedError

    def runs(self) -> list[str]:
        """Run ids, in the order they were first recorded."""
        raise NotImplementedError

    def outcomes(self) -> list[tuple[str, str, Outcome]]:
        """(run_id, pipeline, outcome) for everything stored, in the order it was recorded."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
