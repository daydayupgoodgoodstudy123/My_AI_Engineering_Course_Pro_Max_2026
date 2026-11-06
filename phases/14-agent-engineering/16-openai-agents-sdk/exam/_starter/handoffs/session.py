"""Conversation history per session, kept in SQLite."""
from __future__ import annotations

import sqlite3

from .items import Item


class SQLiteSession:
    """The conversation history of one session id, in a SQLite file that many sessions share.

    A session holds UserMessage, AssistantMessage, ToolItem and HandoffItem items. They come back
    exactly as they were added: the same item types and field values, oldest first. A ToolItem's
    args are written as JSON text with json.dumps, keys in the order they were inserted (no
    sort_keys), and read back with json.loads, so they keep their key order and number types.
    """

    def __init__(self, session_id: str, path: str = ":memory:") -> None:
        self.session_id = session_id
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def get_items(self, limit: int | None = None) -> list[Item]:
        """This session's items, oldest first. With a limit, only the latest limit items, still
        oldest first."""
        raise NotImplementedError

    def add_items(self, items: list[Item]) -> None:
        """Append items to this session in one go. If one of them is not a session item, raise
        TypeError and store none of them."""
        raise NotImplementedError

    def pop_item(self) -> Item | None:
        """Remove this session's latest item and return it; None when the session is empty."""
        raise NotImplementedError

    def clear_session(self) -> None:
        """Remove every item of this session. Other sessions keep theirs."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
