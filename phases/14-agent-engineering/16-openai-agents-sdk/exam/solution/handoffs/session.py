"""Conversation history per session, kept in SQLite."""
from __future__ import annotations

import dataclasses
import json
import sqlite3

from .items import AssistantMessage, HandoffItem, Item, ToolItem, UserMessage

KINDS = {"user": UserMessage, "assistant": AssistantMessage, "tool": ToolItem, "handoff": HandoffItem}

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS items (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        body TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS items_by_session ON items (session_id, seq)",
)


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
        with self._db:
            for statement in SCHEMA:
                self._db.execute(statement)

    def get_items(self, limit: int | None = None) -> list[Item]:
        """This session's items, oldest first. With a limit, only the latest limit items, still
        oldest first."""
        if limit is None:
            rows = self._db.execute(
                "SELECT kind, body FROM items WHERE session_id = ? ORDER BY seq", (self.session_id,)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT kind, body FROM items WHERE session_id = ? ORDER BY seq DESC LIMIT ?",
                (self.session_id, limit),
            ).fetchall()[::-1]
        return [_load(kind, body) for kind, body in rows]

    def add_items(self, items: list[Item]) -> None:
        """Append items to this session in one go. If one of them is not a session item, raise
        TypeError and store none of them."""
        rows = [(self.session_id, *_dump(item)) for item in items]
        with self._db:
            self._db.executemany("INSERT INTO items (session_id, kind, body) VALUES (?, ?, ?)", rows)

    def pop_item(self) -> Item | None:
        """Remove this session's latest item and return it; None when the session is empty."""
        row = self._db.execute(
            "SELECT seq, kind, body FROM items WHERE session_id = ? ORDER BY seq DESC LIMIT 1",
            (self.session_id,),
        ).fetchone()
        if row is None:
            return None
        with self._db:
            self._db.execute("DELETE FROM items WHERE seq = ?", (row[0],))
        return _load(row[1], row[2])

    def clear_session(self) -> None:
        """Remove every item of this session. Other sessions keep theirs."""
        with self._db:
            self._db.execute("DELETE FROM items WHERE session_id = ?", (self.session_id,))

    def close(self) -> None:
        self._db.close()


def _dump(item: Item) -> tuple[str, str]:
    for kind, cls in KINDS.items():
        if type(item) is cls:
            return kind, json.dumps(dataclasses.asdict(item), ensure_ascii=False)
    raise TypeError(f"not a session item: {item!r}")


def _load(kind: str, body: str) -> Item:
    return KINDS[kind](**json.loads(body))
