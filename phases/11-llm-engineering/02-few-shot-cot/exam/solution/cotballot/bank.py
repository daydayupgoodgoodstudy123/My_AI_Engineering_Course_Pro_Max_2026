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
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute("""CREATE TABLE IF NOT EXISTS examples (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                question TEXT NOT NULL, reasoning TEXT NOT NULL, answer TEXT NOT NULL,
                label TEXT NOT NULL, difficulty INTEGER NOT NULL)""")

    def put(self, example: dict) -> None:
        """Insert a new id or update its fields while retaining its first corpus position."""
        if set(example) != set(COLUMNS):
            raise ValueError("example fields do not match the corpus contract")
        if any(not isinstance(example[key], str) for key in COLUMNS[:-1]) or not example["id"]:
            raise ValueError("example text fields must be strings and id must not be empty")
        if type(example["difficulty"]) is not int or example["difficulty"] < 0:
            raise ValueError("difficulty must be a nonnegative integer")
        values = tuple(example[key] for key in COLUMNS)
        with self._db:
            self._db.execute("""INSERT INTO examples (id, question, reasoning, answer, label, difficulty)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
                question=excluded.question, reasoning=excluded.reasoning, answer=excluded.answer,
                label=excluded.label, difficulty=excluded.difficulty""", values)

    def get(self, example_id: str) -> dict:
        """Return a fresh example dict; an unknown id raises KeyError."""
        row = self._db.execute("SELECT id, question, reasoning, answer, label, difficulty FROM examples WHERE id = ?",
                               (example_id,)).fetchone()
        if row is None:
            raise KeyError(example_id)
        return dict(zip(COLUMNS, row))

    def examples(self, label: str | None = None) -> list[dict]:
        """Return fresh dicts in original corpus order, optionally filtered by exact label."""
        query = "SELECT id, question, reasoning, answer, label, difficulty FROM examples"
        params = ()
        if label is not None:
            query += " WHERE label = ?"
            params = (label,)
        return [dict(zip(COLUMNS, row)) for row in self._db.execute(query + " ORDER BY seq", params)]

    def close(self) -> None:
        self._db.close()
