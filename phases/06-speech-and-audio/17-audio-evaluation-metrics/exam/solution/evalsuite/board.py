"""A leaderboard of evaluation results, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .metrics import METRICS

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    benchmark TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    n INTEGER NOT NULL,
    ci_low REAL NOT NULL,
    ci_high REAL NOT NULL,
    protocol TEXT NOT NULL,
    UNIQUE (model, benchmark, metric)
)
"""
COLUMNS = "model, benchmark, metric, value, n, ci_low, ci_high, protocol"


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
        with self._db:
            self._db.execute(SCHEMA)

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
        spec = METRICS.get(metric)
        if spec is None:
            raise ValueError(f"unknown metric {metric!r}")
        if not spec.minimum <= value <= spec.maximum:
            raise ValueError(f"{metric} must lie in [{spec.minimum}, {spec.maximum}], got {value}")
        low, high = ci
        if not low <= value <= high:
            raise ValueError(f"interval {ci} does not contain {value}")
        if not isinstance(n, int) or n < 1:
            raise ValueError(f"n must be a positive number of test items, got {n!r}")
        with self._db:
            self._db.execute(
                f"INSERT INTO results ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (model, benchmark, metric) DO UPDATE SET"
                " value = excluded.value, n = excluded.n, ci_low = excluded.ci_low,"
                " ci_high = excluded.ci_high, protocol = excluded.protocol",
                (model, benchmark, metric, value, n, low, high, protocol),
            )

    def get(self, model: str, benchmark: str, metric: str) -> Entry:
        """The current result. Unknown keys raise KeyError."""
        row = self._db.execute(
            f"SELECT {COLUMNS} FROM results WHERE model = ? AND benchmark = ? AND metric = ?",
            (model, benchmark, metric),
        ).fetchone()
        if row is None:
            raise KeyError((model, benchmark, metric))
        return _entry(row)

    def ranking(self, benchmark: str, metric: str) -> list[Entry]:
        """Results for one benchmark and metric, best first, in the metric's direction.

        Equal values keep the order in which the models first appeared there. Results computed
        under different protocols are not comparable, and ranking them raises ValueError.
        """
        spec = METRICS.get(metric)
        if spec is None:
            raise ValueError(f"unknown metric {metric!r}")
        order = "ASC" if spec.lower_is_better else "DESC"
        entries = [
            _entry(row)
            for row in self._db.execute(
                f"SELECT {COLUMNS} FROM results WHERE benchmark = ? AND metric = ?"
                f" ORDER BY value {order}, seq",
                (benchmark, metric),
            )
        ]
        protocols = sorted({entry.protocol for entry in entries})
        if len(protocols) > 1:
            raise ValueError(f"{benchmark} {metric} mixes protocols {protocols}")
        return entries

    def close(self) -> None:
        self._db.close()


def _entry(row: tuple) -> Entry:
    model, benchmark, metric, value, n, low, high, protocol = row
    return Entry(model, benchmark, metric, value, n, (low, high), protocol)
