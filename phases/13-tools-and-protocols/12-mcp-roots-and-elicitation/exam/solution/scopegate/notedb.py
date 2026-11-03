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
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS claims ("
                " nonce TEXT PRIMARY KEY,"
                " expires_at REAL NOT NULL)"
            )

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
        with self._db:
            self._claim(nonce, expires_at)

    def claim_and_delete(self, nonce: str, *, expires_at: float, note_id: str, workspace_uri: str) -> None:
        """Consume a nonce and delete the confirmed note, in one transaction.

        The nonce is claimed first and fails like claim(), whatever note is named. The live
        note is then re-checked inside the same transaction: McpError(-32602, "selected
        note no longer exists") or McpError(-32602, "selected note is outside workspace")
        when it does not pass. After any failure the nonce and the notes are unchanged.
        """
        with self._db:
            self._claim(nonce, expires_at)
            row = self._db.execute("SELECT uri FROM notes WHERE note_id = ?", (note_id,)).fetchone()
            if row is None:
                raise McpError(-32602, "selected note no longer exists")
            if not uri_within_workspace(workspace_uri, row[0]):
                raise McpError(-32602, "selected note is outside workspace")
            self._db.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))

    def _claim(self, nonce: str, expires_at: float) -> None:
        if expires_at <= self._clock():
            raise McpError(-32602, "requestState expired")
        inserted = self._db.execute(
            "INSERT INTO claims (nonce, expires_at) VALUES (?, ?) ON CONFLICT (nonce) DO NOTHING",
            (nonce, expires_at),
        ).rowcount
        if inserted != 1:
            raise McpError(-32602, "requestState was already consumed")

    def claims(self) -> dict[str, float]:
        """Every claim still kept, as {nonce: expires_at}."""
        return dict(self._db.execute("SELECT nonce, expires_at FROM claims ORDER BY rowid"))

    def prune(self) -> int:
        """Drop the claims whose state has expired (expires_at <= clock()). Return how many."""
        with self._db:
            return self._db.execute("DELETE FROM claims WHERE expires_at <= ?", (self._clock(),)).rowcount

    def close(self) -> None:
        self._db.close()
