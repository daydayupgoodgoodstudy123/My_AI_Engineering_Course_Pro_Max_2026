"""Captured content in SQLite. Spans carry only the row id ("references only" mode)."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    body TEXT NOT NULL UNIQUE
)
"""


class SqliteContentStore:
    """Content store for Tracer(content_store=...), backed by one SQLite file.

    Content is any JSON value: a string, or gen_ai.input.messages as a list of message
    dicts. It comes back exactly as it went in, with the same types all the way down
    (a str stays a str even when it looks like JSON; 1, 1.0 and True stay distinct).

    put() returns the content row's id as a decimal string. Content that is exactly the same
    (same JSON text) reuses its row, also after a reopen. A deleted reference is never handed
    out again, so an old span can never point at someone else's content.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def put(self, content: Any) -> str:
        """Store content (or find its row) and return the reference."""
        body = json.dumps(content)
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO content (body) VALUES (?)", (body,))
            (row_id,) = self._db.execute("SELECT id FROM content WHERE body = ?", (body,)).fetchone()
        return str(row_id)

    def get(self, ref: str) -> Any:
        """Return the content behind ref. Unknown references raise KeyError."""
        row = self._db.execute("SELECT body FROM content WHERE id = ?", (_row_id(ref),)).fetchone()
        if row is None:
            raise KeyError(ref)
        return json.loads(row[0])

    def delete(self, ref: str) -> None:
        """Erase the content behind ref (a deletion request). Unknown references raise KeyError."""
        with self._db:
            cur = self._db.execute("DELETE FROM content WHERE id = ?", (_row_id(ref),))
        if cur.rowcount == 0:
            raise KeyError(ref)

    def close(self) -> None:
        self._db.close()


def _row_id(ref: str) -> int:
    if not (isinstance(ref, str) and ref.isascii() and ref.isdigit()):
        raise KeyError(ref)
    return int(ref)
