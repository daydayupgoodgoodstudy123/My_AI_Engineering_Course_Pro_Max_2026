"""Long-term memory that remembers where every note came from, stored in SQLite."""
from __future__ import annotations

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


class MemoryStore:
    """Notes the agent keeps across sessions.

    A note is tainted when its own source is not user_message, or when any note it was derived
    from is tainted. Taint never wears off, however many summaries away the text gets.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def write(self, text: str, source: str, derived_from: Iterable[int] = ()) -> Note:
        """Store a note exactly as written and return it. Ids count up from 1.

        source must be one of SOURCES (ValueError). Text that looks like a directive is refused
        with MemoryRefused, whatever its source. An unknown id in derived_from raises KeyError.
        A refused write stores nothing.
        """
        raise NotImplementedError

    def get(self, note_id: int) -> Note:
        """Return one note. Unknown ids raise KeyError."""
        raise NotImplementedError

    def notes(self) -> list[Note]:
        """Every note, oldest first."""
        raise NotImplementedError

    def recall(self) -> list[Content]:
        """Every note as context for the next session, oldest first, with its source and taint."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
