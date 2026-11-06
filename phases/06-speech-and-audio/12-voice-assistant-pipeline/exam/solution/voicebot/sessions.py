"""Conversation history per session, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3

ROLES = ("system", "user", "assistant", "tool")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    at REAL NOT NULL,
    message TEXT NOT NULL
)
"""
INDEX = "CREATE INDEX IF NOT EXISTS messages_by_session ON messages (session_id, seq)"


class SessionStore:
    """Chat history per session.

    Messages are chat-API dicts. They come back exactly as they were appended, in order, whatever
    provider format they use: tool-call arguments as a dict or as JSON text, content None next to
    tool calls, extra keys.

    A session expires ttl_s seconds after its last message. An expired session has no history, and
    the next message appended to it starts a new conversation, deleting the old one. Transcripts are
    personal data: deleted messages must not stay readable in the database file.
    """

    def __init__(self, path: str = ":memory:", ttl_s: float = 600.0) -> None:
        self.ttl_s = ttl_s
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA secure_delete = ON")
        with self._db:
            self._db.execute(SCHEMA)
            self._db.execute(INDEX)

    def append(self, session_id: str, message: dict, now: float) -> None:
        """Add one message at time now (seconds). The role must be one of ROLES."""
        if message.get("role") not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {message.get('role')!r}")
        with self._db:
            if self._expired(session_id, now):
                self._db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._db.execute(
                "INSERT INTO messages (session_id, at, message) VALUES (?, ?, ?)",
                (session_id, now, json.dumps(message)),
            )

    def history(self, session_id: str, now: float) -> list[dict]:
        """The session's messages in the order appended; [] if it is unknown or expired."""
        if self._expired(session_id, now):
            return []
        rows = self._db.execute(
            "SELECT message FROM messages WHERE session_id = ? ORDER BY seq", (session_id,)
        )
        return [json.loads(text) for (text,) in rows]

    def purge(self, now: float) -> int:
        """Delete every expired session and return how many messages were deleted."""
        with self._db:
            cursor = self._db.execute(
                "DELETE FROM messages WHERE session_id IN ("
                " SELECT session_id FROM messages GROUP BY session_id HAVING MAX(at) <= ?)",
                (now - self.ttl_s,),
            )
        return cursor.rowcount

    def close(self) -> None:
        self._db.close()

    def _expired(self, session_id: str, now: float) -> bool:
        (last,) = self._db.execute(
            "SELECT MAX(at) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        return last is not None and now - last >= self.ttl_s
