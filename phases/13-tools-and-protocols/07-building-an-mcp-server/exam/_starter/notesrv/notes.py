"""Notes, their notes:// URIs, and the in-memory note store."""
from __future__ import annotations

from dataclasses import dataclass

NOTE_SCHEME = "notes://"


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    body: str
    tag: str = ""
    owner: str | None = None  # the principal that created the note; None when nobody owns it


def note_uri(note_id: str) -> str:
    return NOTE_SCHEME + note_id


def note_id_from_uri(uri: str) -> str:
    """The note id inside a notes:// URI: notes://note-7 names note-7."""
    return uri.lstrip(NOTE_SCHEME)


SAMPLE_NOTES = (
    ("MCP overview", "Stateless requests and JSON-RPC.", "mcp"),
    ("Function calling", "Provider envelopes differ.", "api"),
    ("Tool schemas", "Atomic tools are easier to route.", "design"),
)


class MemoryNotes:
    """Notes held in memory. It starts with the three sample notes, which nobody owns.

    Ids are note-1, note-2, ... in creation order. An id is never handed out twice, not even
    after its note is deleted: clients cache resources by URI, and a reused URI would show
    them a different note.
    """

    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}
        for title, body, tag in SAMPLE_NOTES:
            self.create(title, body, tag)

    def create(self, title: str, body: str, tag: str = "", owner: str | None = None) -> Note:
        number = 1 + max((int(note_id.removeprefix("note-")) for note_id in self._notes), default=0)
        note = Note(f"note-{number}", title, body, tag, owner)
        self._notes[note.id] = note
        return note

    def get(self, note_id: str) -> Note:
        """The note with this id. Unknown ids raise KeyError."""
        return self._notes[note_id]

    def delete(self, note_id: str) -> None:
        """Remove a note. Unknown ids raise KeyError."""
        del self._notes[note_id]

    def all(self) -> list[Note]:
        """Every note, oldest first."""
        return list(self._notes.values())
