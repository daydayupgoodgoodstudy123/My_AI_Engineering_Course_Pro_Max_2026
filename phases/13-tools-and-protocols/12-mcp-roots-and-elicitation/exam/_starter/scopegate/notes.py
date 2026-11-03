"""Notes kept in memory, the way the lesson's server keeps them."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .scope import uri_within_workspace


@dataclass(frozen=True)
class Note:
    note_id: str
    title: str
    uri: str


class NoteBook:
    """Notes in insertion order. Several server objects may share one NoteBook."""

    def __init__(self, notes: Iterable[Note] = ()) -> None:
        self._notes: dict[str, Note] = {}
        for note in notes:
            self.add(note)

    def add(self, note: Note) -> None:
        if note.note_id in self._notes:
            raise ValueError(f"duplicate note id {note.note_id!r}")
        self._notes[note.note_id] = note

    def get(self, note_id: str) -> Note | None:
        return self._notes.get(note_id)

    def delete(self, note_id: str) -> None:
        """Remove a note. An unknown id raises KeyError."""
        del self._notes[note_id]

    def move(self, note_id: str, uri: str) -> None:
        """Give a note a new URI. It keeps its place in the order."""
        self._notes[note_id] = replace(self._notes[note_id], uri=uri)

    def all(self) -> list[Note]:
        return list(self._notes.values())

    def matching(self, workspace_uri: str, title: str) -> list[Note]:
        """Notes inside the workspace whose title contains title, ignoring case, in order."""
        needle = title.casefold()
        return [
            note
            for note in self._notes.values()
            if needle in note.title.casefold() and uri_within_workspace(workspace_uri, note.uri)
        ]
