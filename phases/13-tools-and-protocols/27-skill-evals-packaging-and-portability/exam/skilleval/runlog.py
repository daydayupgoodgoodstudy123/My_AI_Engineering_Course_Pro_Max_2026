"""Raw per-run trigger observations, kept in a CSV file so that traces can guide repair."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from .cases import CATEGORIES, is_skill_name

COLUMNS = ("case_id", "run", "category", "predicted_skill", "latency_ms", "trace")


@dataclass(frozen=True)
class RunObservation:
    """What the target runtime did on one run of one trigger case.

    predicted_skill is the skill the router invoked, or None when it abstained. latency_ms is the
    measured latency in milliseconds, a float. trace is the host's raw output for the run.
    """

    case_id: str
    run: int
    category: str
    predicted_skill: str | None
    latency_ms: float
    trace: str


class ObservationLog:
    """An append-only CSV file of run observations: a header row with COLUMNS, then one row per run.

    Runs are appended as they finish, so a case's rows can arrive in any order, and other workers
    may append to the same file. An abstention is an empty predicted_skill cell. latency_ms is
    written so that float() gives back exactly the same float, and trace is kept character for
    character, commas, quotes and line breaks included.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, observation: RunObservation) -> None:
        """Add one run.

        A malformed observation raises ValueError and leaves the file as it was: case_id must be
        non-empty without surrounding whitespace, run a non-negative int, category one of
        CATEGORIES, predicted_skill a skill name or None (an empty string is not an abstention),
        and latency_ms a finite, non-negative float.
        """
        raise NotImplementedError

    def load(self) -> dict[str, list[RunObservation]]:
        """Every logged case's runs, in run order.

        A run logged twice, or a case whose runs are not exactly 0..n-1, raises ValueError.
        A log that does not exist yet is empty.
        """
        raise NotImplementedError
