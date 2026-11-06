"""Archival memory that survives a restart, stored in SQLite.

Records live in a table named archival, and its turn_id column is declared INTEGER. How records
are keyed, and how text, tags and session_id are stored, is up to the implementation.
"""
from __future__ import annotations

import sqlite3

from .archival import ArchivalStore


class SqliteArchive(ArchivalStore):
    """Archival memory backed by a SQLite file. get, records and search work as in ArchivalStore.

    A record comes back exactly as it was inserted, also after the file is closed and reopened:
    the same text, the same tags in the same order (a tuple), session_id a str, turn_id an int.
    Every insert is on disk when insert returns. A deleted record is gone from get, records and
    search, and its id is never handed out again, because old answers cite it.
    """

    def __init__(self, path: str = ":memory:") -> None:
        super().__init__()
        self._db = sqlite3.connect(path)
        # TODO: create the schema, then load the stored records

    def insert(
        self, text: str, *, tags: tuple[str, ...] = (), session_id: str = "s0", turn_id: int = 0
    ) -> str:
        """Store one fact and return its new id."""
        raise NotImplementedError

    def delete(self, rid: str) -> None:
        """Delete a record for good. Unknown ids raise KeyError."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
