"""Notes on disk: a body file and a metadata file per note, plus an id counter."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .notes import Note

_NOTE_ID = re.compile(r"note-([1-9][0-9]*)")


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
        self.root.mkdir(parents=True, exist_ok=True)
        self._counter = self.root / "next_id"

    def create(self, title: str, body: str, tag: str = "", owner: str | None = None) -> Note:
        note = Note(f"note-{self._take_number()}", title, body, tag, owner)
        self._path(note.id, ".body").write_bytes(body.encode("utf-8"))
        meta = {"title": title, "tag": tag, "owner": owner}
        self._path(note.id, ".json").write_text(json.dumps(meta), encoding="utf-8")
        return note

    def get(self, note_id: str) -> Note:
        """The note with this id. Unknown ids raise KeyError."""
        try:
            meta = json.loads(self._path(note_id, ".json").read_bytes())
            body = self._path(note_id, ".body").read_bytes().decode("utf-8")
        except FileNotFoundError:
            raise KeyError(note_id) from None
        return Note(note_id, meta["title"], body, meta["tag"], meta["owner"])

    def delete(self, note_id: str) -> None:
        """Remove a note's files. Unknown ids raise KeyError."""
        try:
            self._path(note_id, ".json").unlink()
        except FileNotFoundError:
            raise KeyError(note_id) from None
        self._path(note_id, ".body").unlink(missing_ok=True)

    def all(self) -> list[Note]:
        """Every note, oldest first."""
        numbers = []
        for path in self.root.glob("note-*.json"):
            match = _NOTE_ID.fullmatch(path.stem)
            if match:
                numbers.append(int(match.group(1)))
        return [self.get(f"note-{number}") for number in sorted(numbers)]

    def _take_number(self) -> int:
        # The counter moves on before the note is written: a crash in between costs a number
        # (a gap) but can never hand the same number out twice.
        number = int(self._counter.read_text(encoding="ascii")) if self._counter.exists() else 1
        self._counter.write_text(str(number + 1), encoding="ascii")
        return number

    def _path(self, note_id: str, suffix: str) -> Path:
        if not isinstance(note_id, str) or not _NOTE_ID.fullmatch(note_id):
            raise KeyError(note_id)
        return self.root / f"{note_id}{suffix}"
