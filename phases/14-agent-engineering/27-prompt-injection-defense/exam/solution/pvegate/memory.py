"""Long-term memory that remembers where every note came from, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from .content import SOURCES, Content, looks_like_directive


class MemoryRefused(ValueError):
    """A memory write that looks like an instruction."""


@dataclass(frozen=True)
class Note:
    note_id: int
    text: str
    source: str
    tainted: bool
    derived_from: tuple[int, ...]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    tainted INTEGER NOT NULL,
    derived_from TEXT NOT NULL
)
"""


class MemoryStore:
    """Notes the agent keeps across sessions.

    A note is tainted when its own source is not user_message, or when any note it was derived
    from is tainted. Taint never wears off, however many summaries away the text gets.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(_SCHEMA)

    def write(self, text: str, source: str, derived_from: Iterable[int] = ()) -> Note:
        """Store a note exactly as written and return it. Ids count up from 1.

        source must be one of SOURCES (ValueError). Text that looks like a directive is refused
        with MemoryRefused, whatever its source. An unknown id in derived_from raises KeyError.
        A refused write stores nothing.
        """
        if source not in SOURCES:
            raise ValueError(f"unknown source {source!r}, expected one of {SOURCES}")
        hit = looks_like_directive(text)
        if hit:
            raise MemoryRefused(f"memory write looks like an instruction: {hit!r}")
        parents = tuple(derived_from)
        tainted = source != "user_message"
        with self._db:
            for parent in parents:
                tainted = self.get(parent).tainted or tainted
            cur = self._db.execute(
                "INSERT INTO notes (text, source, tainted, derived_from) VALUES (?, ?, ?, ?)",
                (text, source, int(tainted), json.dumps(parents)),
            )
        return Note(cur.lastrowid, text, source, tainted, parents)

    def get(self, note_id: int) -> Note:
        """Return one note. Unknown ids raise KeyError."""
        row = self._db.execute(
            "SELECT note_id, text, source, tainted, derived_from FROM notes WHERE note_id = ?",
            (note_id,),
        ).fetchone()
        if row is None:
            raise KeyError(note_id)
        return _note(row)

    def notes(self) -> list[Note]:
        """Every note, oldest first."""
        rows = self._db.execute(
            "SELECT note_id, text, source, tainted, derived_from FROM notes ORDER BY note_id"
        )
        return [_note(row) for row in rows]

    def recall(self) -> list[Content]:
        """Every note as context for the next session, oldest first, with its source and taint."""
        return [Content(n.text, n.source, n.tainted) for n in self.notes()]

    def close(self) -> None:
        self._db.close()


def _note(row: tuple) -> Note:
    note_id, text, source, tainted, derived_from = row
    return Note(note_id, text, source, bool(tainted), tuple(json.loads(derived_from)))
