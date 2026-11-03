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
        _check(observation)
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(COLUMNS)
            writer.writerow(
                [
                    observation.case_id,
                    observation.run,
                    observation.category,
                    "" if observation.predicted_skill is None else observation.predicted_skill,
                    repr(observation.latency_ms),
                    observation.trace,
                ]
            )

    def load(self) -> dict[str, list[RunObservation]]:
        """Every logged case's runs, in run order.

        A run logged twice, or a case whose runs are not exactly 0..n-1, raises ValueError.
        A log that does not exist yet is empty.
        """
        if not self.path.exists():
            return {}
        by_case: dict[str, dict[int, RunObservation]] = {}
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return {}
            if tuple(header) != COLUMNS:
                raise ValueError(f"not an observation log: header {header!r}")
            for row in reader:
                if len(row) != len(COLUMNS):
                    raise ValueError(f"row {reader.line_num} has {len(row)} cells, not {len(COLUMNS)}")
                case_id, run, category, predicted, latency_ms, trace = row
                observation = RunObservation(case_id, int(run), category, predicted or None, float(latency_ms), trace)
                _check(observation)
                runs = by_case.setdefault(case_id, {})
                if observation.run in runs:
                    raise ValueError(f"run {observation.run} of {case_id!r} is logged twice")
                runs[observation.run] = observation
        loaded: dict[str, list[RunObservation]] = {}
        for case_id, runs in by_case.items():
            if sorted(runs) != list(range(len(runs))):
                raise ValueError(f"{case_id!r} has runs {sorted(runs)}, not 0..{len(runs) - 1}")
            loaded[case_id] = [runs[index] for index in range(len(runs))]
        return loaded


def _check(observation: RunObservation) -> None:
    case_id = observation.case_id
    if not isinstance(case_id, str) or not case_id.strip() or case_id != case_id.strip():
        raise ValueError("case_id must be non-empty, without surrounding whitespace")
    if type(observation.run) is not int or observation.run < 0:
        raise ValueError(f"{case_id!r}: run must be a non-negative int")
    if observation.category not in CATEGORIES:
        raise ValueError(f"{case_id!r}: unknown category {observation.category!r}")
    if observation.predicted_skill is not None and not is_skill_name(observation.predicted_skill):
        raise ValueError(f"{case_id!r}: {observation.predicted_skill!r} is not a skill name; an abstention is None")
    latency = observation.latency_ms
    if type(latency) is not float or not math.isfinite(latency) or latency < 0:
        raise ValueError(f"{case_id!r}: latency_ms must be a finite, non-negative float")
    if not isinstance(observation.trace, str):
        raise ValueError(f"{case_id!r}: trace must be text")
