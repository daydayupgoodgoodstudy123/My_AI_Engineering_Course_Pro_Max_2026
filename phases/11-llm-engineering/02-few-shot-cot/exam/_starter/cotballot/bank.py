"""SQLite corpus of worked examples with lossless textual answers."""
from __future__ import annotations

import sqlite3


COLUMNS = ("id", "question", "reasoning", "answer", "label", "difficulty")


class ExampleBank:
    """Persist example dicts, preserving original corpus order across updates.

    A dict has the six COLUMNS. The five textual fields are strings; id is
    nonempty, difficulty is a nonnegative integer. Answers are stored exactly
    as supplied, never converted to floats or canonical ballot values.
    """

    def __init__(self, path: str = ":memory:") -> None:
        raise NotImplementedError

    def put(self, example: dict) -> None:
        """Insert a new id or update its fields while retaining its first corpus position."""
        raise NotImplementedError

    def get(self, example_id: str) -> dict:
        """Return a fresh example dict; an unknown id raises KeyError."""
        raise NotImplementedError

    def examples(self, label: str | None = None) -> list[dict]:
        """Return fresh dicts in original corpus order, optionally filtered by exact label."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
