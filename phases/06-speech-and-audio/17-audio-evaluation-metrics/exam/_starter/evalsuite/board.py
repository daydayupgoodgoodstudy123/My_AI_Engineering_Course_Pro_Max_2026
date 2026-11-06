"""A leaderboard of evaluation results, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .metrics import METRICS


@dataclass(frozen=True)
class Entry:
    model: str
    benchmark: str
    metric: str
    value: float
    n: int  # test items the value was computed on
    ci: tuple[float, float]  # (low, high) confidence interval of value
    protocol: str  # how value was computed, e.g. the text normalizer behind a WER


class Leaderboard:
    """One result per (model, benchmark, metric)."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def submit(
        self,
        model: str,
        benchmark: str,
        metric: str,
        value: float,
        n: int,
        ci: tuple[float, float],
        protocol: str,
    ) -> None:
        """Record a result; submitting the same (model, benchmark, metric) again replaces it.

        metric is a key of METRICS and value lies in that metric's valid range; n >= 1 is the
        number of test items; ci = (low, high) with low <= value <= high. Bad input raises
        ValueError. A replaced result keeps the model's place on its benchmark and metric.
        """
        raise NotImplementedError

    def get(self, model: str, benchmark: str, metric: str) -> Entry:
        """The current result. Unknown keys raise KeyError."""
        raise NotImplementedError

    def ranking(self, benchmark: str, metric: str) -> list[Entry]:
        """Results for one benchmark and metric, best first, in the metric's direction.

        Equal values keep the order in which the models first appeared there. Results computed
        under different protocols are not comparable, and ranking them raises ValueError.
        """
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
