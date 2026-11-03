"""Notes and consumed confirmation nonces in one SQLite file.

This is the production shape of NoteBook plus ReplayStore, for a server that runs as
several processes: each process opens its own NoteDB on the shared file.
"""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable

from .notes import Note
from .protocol import McpError
from .scope import uri_within_workspace


class NoteDB:
    """Notes and claimed nonces, shared through one SQLite file.

    A nonce is claimed at most once across every NoteDB on the file, and the claim that
    confirms a deletion commits together with that deletion or not at all.
    """

    def __init__(self, path: str, *, clock: Callable[[], float] = time.time) -> None:
        self._db = sqlite3.connect(path)
        self._clock = clock
        with self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS notes ("
                " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                " note_id TEXT NOT NULL UNIQUE,"
                " title TEXT NOT NULL,"
                " uri TEXT NOT NULL)"
            )
        # TODO: a table for claimed nonces

    def add_note(self, note: Note) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO notes (note_id, title, uri) VALUES (?, ?, ?)",
                (note.note_id, note.title, note.uri),
            )

    def note(self, note_id: str) -> Note | None:
        row = self._db.execute(
            "SELECT note_id, title, uri FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        return Note(*row) if row else None

    def notes(self) -> list[Note]:
        """Every note, oldest first."""
        return [Note(*row) for row in self._db.execute("SELECT note_id, title, uri FROM notes ORDER BY seq")]

    def claim(self, nonce: str, *, expires_at: float) -> None:
        """Consume a nonce without touching any note, as an explicit decline does.

        An expired state (expires_at <= clock()) raises McpError(-32602, "requestState
        expired") and claims nothing. A nonce that is already claimed, by this NoteDB or
        any other on the file, raises McpError(-32602, "requestState was already consumed").
        """
        raise NotImplementedError

    def claim_and_delete(self, nonce: str, *, expires_at: float, note_id: str, workspace_uri: str) -> None:
        """Consume a nonce and delete the confirmed note, in one transaction.

        The nonce is claimed first and fails like claim(), whatever note is named. The live
        note is then re-checked inside the same transaction: McpError(-32602, "selected
        note no longer exists") or McpError(-32602, "selected note is outside workspace")
        when it does not pass. After any failure the nonce and the notes are unchanged.
        """
        raise NotImplementedError

    def claims(self) -> dict[str, float]:
        """Every claim still kept, as {nonce: expires_at}."""
        raise NotImplementedError

    def prune(self) -> int:
        """Drop the claims whose state has expired (expires_at <= clock()). Return how many."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
