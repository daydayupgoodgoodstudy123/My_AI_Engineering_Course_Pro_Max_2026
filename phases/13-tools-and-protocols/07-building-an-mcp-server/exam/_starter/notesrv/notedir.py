"""Notes on disk: a body file and a metadata file per note, plus an id counter."""
from __future__ import annotations

import json
from pathlib import Path

from .notes import Note


class NoteDir:
    """A note store kept in one directory, so notes outlive the server process.

    Layout under root (created if missing):
        note-<n>.body   the note's body: exactly its UTF-8 bytes, nothing added or removed
        note-<n>.json   the rest of the note: {"title": ..., "tag": ..., "owner": ...}
        next_id         the counter that numbers new notes

    The interface is MemoryNotes'. Ids are note-1, note-2, ...; a number is never handed out
    twice, even after its note was deleted and the store reopened. Gaps are fine.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def create(self, title: str, body: str, tag: str = "", owner: str | None = None) -> Note:
        raise NotImplementedError

    def get(self, note_id: str) -> Note:
        """The note with this id. Unknown ids raise KeyError."""
        raise NotImplementedError

    def delete(self, note_id: str) -> None:
        """Remove a note's files. Unknown ids raise KeyError."""
        raise NotImplementedError

    def all(self) -> list[Note]:
        """Every note, oldest first."""
        raise NotImplementedError
