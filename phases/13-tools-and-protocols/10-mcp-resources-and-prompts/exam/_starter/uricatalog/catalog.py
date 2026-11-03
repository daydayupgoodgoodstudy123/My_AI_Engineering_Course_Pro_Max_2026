"""Notes addressed by notes:// URIs, and who may read them."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Caller:
    """Whoever the transport authenticated for one request. It is never read from the request."""

    tenant: str
    user: str


@dataclass(frozen=True)
class Note:
    uri: str
    name: str
    description: str
    text: str
    tenant: str
    readers: frozenset[str] = frozenset()  # empty: every user of the tenant may read the note
    mime_type: str = "text/markdown"

    def readable_by(self, caller: Caller) -> bool:
        return caller.tenant == self.tenant and (not self.readers or caller.user in self.readers)


class Catalog:
    """The notes one server exposes, keyed by URI, in the order they were added."""

    def __init__(self, notes: tuple[Note, ...] | list[Note] = ()) -> None:
        self._notes: dict[str, Note] = {}
        for note in notes:
            self.put(note)

    def put(self, note: Note) -> None:
        self._notes[note.uri] = note

    def remove(self, uri: str) -> None:
        del self._notes[uri]

    def get(self, uri: str) -> Note | None:
        return self._notes.get(uri)

    def notes(self) -> list[Note]:
        return list(self._notes.values())


def sample_catalog() -> Catalog:
    """Four notes for acme, one of them only for alice, and one note for another tenant."""
    return Catalog(
        [
            Note(
                "notes://note-2",
                "Release checklist",
                "Checks to run before publishing",
                "# Release\n\n- Run tests\n- Confirm the tag",
                "acme",
            ),
            Note(
                "notes://note-1",
                "Architecture decision",
                "Why the service uses a stateless protocol boundary",
                "# Decision\n\nKeep protocol requests self-contained.",
                "acme",
            ),
            Note(
                "notes://note-10",
                "Incident review",
                "What broke during the June outage",
                "# Incident\n\nA shared cache served one user's note to another.",
                "acme",
            ),
            Note(
                "notes://note-3",
                "Salary bands",
                "Compensation notes for next year's plan",
                "# Salary bands\n\nConfidential: the L5 band moves to 210k.",
                "acme",
                readers=frozenset({"alice"}),
            ),
            Note(
                "notes://note-7",
                "Globex roadmap",
                "Another tenant's plan",
                "# Roadmap\n\nGlobex only.",
                "globex",
            ),
        ]
    )
