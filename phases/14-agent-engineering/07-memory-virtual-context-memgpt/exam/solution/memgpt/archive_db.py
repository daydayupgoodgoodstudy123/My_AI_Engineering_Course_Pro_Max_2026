"""Archival memory that survives a restart, stored in SQLite.

Records live in a table named archival, and its turn_id column is declared INTEGER. How records
are keyed, and how text, tags and session_id are stored, is up to the implementation.
"""
from __future__ import annotations

import json
import sqlite3

from .archival import ArchivalRecord, ArchivalStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS archival (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    tags TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_id INTEGER NOT NULL
)
"""


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
        with self._db:
            self._db.execute(SCHEMA)
        self._load()

    def _load(self) -> None:
        ArchivalStore.__init__(self)
        rows = self._db.execute(
            "SELECT seq, text, tags, session_id, turn_id FROM archival ORDER BY seq"
        ).fetchall()
        for seq, text, tags, session_id, turn_id in rows:
            self._keep(ArchivalRecord(_rid(seq), text, tuple(json.loads(tags)), session_id, turn_id))

    def insert(
        self, text: str, *, tags: tuple[str, ...] = (), session_id: str = "s0", turn_id: int = 0
    ) -> str:
        """Store one fact and return its new id."""
        tags = tuple(tags)
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO archival (text, tags, session_id, turn_id) VALUES (?, ?, ?, ?)",
                (text, json.dumps(list(tags)), session_id, turn_id),
            )
        rid = _rid(cursor.lastrowid)
        self._keep(ArchivalRecord(rid, text, tags, session_id, turn_id))
        return rid

    def delete(self, rid: str) -> None:
        """Delete a record for good. Unknown ids raise KeyError."""
        self.get(rid)
        with self._db:
            self._db.execute("DELETE FROM archival WHERE seq = ?", (int(rid[1:]),))
        self._load()

    def close(self) -> None:
        self._db.close()


def _rid(seq: int) -> str:
    return f"a{seq:03d}"
