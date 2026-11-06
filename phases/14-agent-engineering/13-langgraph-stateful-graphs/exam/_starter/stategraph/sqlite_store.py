"""Checkpoints in a SQLite file, with channel values in a typed JSON encoding."""
from __future__ import annotations

import sqlite3
from typing import Any

from .checkpoint import Record


def dumps(value: Any) -> str:
    """Encode a channel value as JSON text that loads() turns back into an equal value of the same types.

    Values are built from None, bool, int, float, str, bytes, list, tuple, set, frozenset and
    dict, with dict keys of any of these hashable types. Anything else raises TypeError.
    """
    raise NotImplementedError


def loads(text: str) -> Any:
    """The value dumps() encoded."""
    raise NotImplementedError


class SQLiteCheckpointer:
    """The checkpointer interface (put, records) on a SQLite file.

    A store opened on the same file later sees every record put before. A put is all or
    nothing: a value dumps() cannot encode raises TypeError and leaves no trace of the step.
    A session's steps are written once each, in order; anything else raises ValueError.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def put(self, session: str, record: Record) -> None:
        raise NotImplementedError

    def records(self, session: str) -> list[Record]:
        """The session's records in step order; empty for a session with none."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
