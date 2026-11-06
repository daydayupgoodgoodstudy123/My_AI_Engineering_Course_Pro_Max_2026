"""Raw model outputs from benchmark runs, one per (model, item), stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    item_id TEXT NOT NULL,
    output TEXT,
    UNIQUE (model, item_id)
)
"""


@dataclass(frozen=True)
class Prediction:
    model: str
    item_id: str
    output: str | None


class ResultStore:
    """What each model answered on each benchmark item.

    A prediction keeps the model's raw output exactly as it came back, because the official
    scorer reads that text. output is None when the call failed.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def record(self, model: str, item_id: str, output: str | None) -> None:
        """Store one raw output. Recording a (model, item) pair again is a rerun: it replaces
        the earlier output and never adds a second prediction."""
        with self._db:
            self._db.execute(
                "INSERT INTO predictions (model, item_id, output) VALUES (?, ?, ?)"
                " ON CONFLICT (model, item_id) DO UPDATE SET output = excluded.output",
                (model, item_id, output),
            )

    def predictions(self, model: str) -> list[Prediction]:
        """A model's predictions, in the order their items were first recorded."""
        rows = self._db.execute(
            "SELECT model, item_id, output FROM predictions WHERE model = ? ORDER BY seq", (model,)
        )
        return [Prediction(*row) for row in rows]

    def pending(self, model: str, item_ids: list[str]) -> list[str]:
        """The given items, in order, that the model still has to answer: never recorded, or
        failed (None). An empty answer is an answer."""
        answered = {
            item_id
            for (item_id,) in self._db.execute(
                "SELECT item_id FROM predictions WHERE model = ? AND output IS NOT NULL", (model,)
            )
        }
        return [item_id for item_id in item_ids if item_id not in answered]

    def close(self) -> None:
        self._db.close()
