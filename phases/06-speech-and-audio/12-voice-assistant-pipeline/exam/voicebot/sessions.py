"""Conversation history per session, stored in SQLite."""
from __future__ import annotations

import sqlite3

ROLES = ("system", "user", "assistant", "tool")


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
        # TODO: create the schema

    def append(self, session_id: str, message: dict, now: float) -> None:
        """Add one message at time now (seconds). The role must be one of ROLES."""
        raise NotImplementedError

    def history(self, session_id: str, now: float) -> list[dict]:
        """The session's messages in the order appended; [] if it is unknown or expired."""
        raise NotImplementedError

    def purge(self, now: float) -> int:
        """Delete every expired session and return how many messages were deleted."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
