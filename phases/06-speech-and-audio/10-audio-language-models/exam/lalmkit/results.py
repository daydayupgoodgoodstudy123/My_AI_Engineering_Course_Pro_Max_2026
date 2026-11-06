"""Raw model outputs from benchmark runs, one per (model, item), stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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
        # TODO: create the schema

    def record(self, model: str, item_id: str, output: str | None) -> None:
        """Store one raw output. Recording a (model, item) pair again is a rerun: it replaces
        the earlier output and never adds a second prediction."""
        raise NotImplementedError

    def predictions(self, model: str) -> list[Prediction]:
        """A model's predictions, in the order their items were first recorded."""
        raise NotImplementedError

    def pending(self, model: str, item_ids: list[str]) -> list[str]:
        """The given items, in order, that the model still has to answer: never recorded, or
        failed (None). An empty answer is an answer."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
