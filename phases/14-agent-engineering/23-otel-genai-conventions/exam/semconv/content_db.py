"""Captured content in SQLite. Spans carry only the row id ("references only" mode)."""
from __future__ import annotations

import sqlite3
from typing import Any


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
        # TODO: create the schema

    def put(self, content: Any) -> str:
        """Store content (or find its row) and return the reference."""
        raise NotImplementedError

    def get(self, ref: str) -> Any:
        """Return the content behind ref. Unknown references raise KeyError."""
        raise NotImplementedError

    def delete(self, ref: str) -> None:
        """Erase the content behind ref (a deletion request). Unknown references raise KeyError."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()

