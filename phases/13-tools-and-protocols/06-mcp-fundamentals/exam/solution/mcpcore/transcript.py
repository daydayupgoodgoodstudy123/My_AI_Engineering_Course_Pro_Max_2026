"""A transcript of the messages that crossed the wire, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

DIRECTIONS = ("client", "server")


class _NoId:
    _instance: _NoId | None = None

    def __new__(cls) -> _NoId:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NO_ID"


NO_ID = _NoId()  # the message has no "id" member (a notification, or a line that is not JSON)


@dataclass(frozen=True)
class Entry:
    seq: int  # the message's position in the transcript
    direction: str  # who sent it: "client" or "server"
    raw: bytes  # the line exactly as it crossed the wire
    method: str | None  # the "method" member, when it is a string
    id: Any  # the "id" member's JSON value (None for null), or NO_ID


def parse_fields(raw: bytes) -> tuple[str | None, Any]:
    """The method and id of one raw line. A line that is not a JSON object has neither."""
    try:
        message = json.loads(raw)
    except ValueError:
        return None, NO_ID
    if not isinstance(message, dict):
        return None, NO_ID
    method = message.get("method")
    return (method if isinstance(method, str) else None), message.get("id", NO_ID)


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY,
    direction TEXT NOT NULL,
    raw BLOB NOT NULL,
    method TEXT,
    id_json TEXT
)
"""


def _id_json(value: Any) -> str | None:
    # JSON text keeps 7 apart from "7", null apart from a missing id, and ids past 64 bits.
    return None if value is NO_ID else json.dumps(value, sort_keys=True)


class Transcript:
    """Every message of a session, in seq order, exactly as it was sent."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def record(self, seq: int, direction: str, raw: bytes) -> Entry:
        """Store one line as it crossed the wire and return its entry.

        Messages may be recorded in any order; seq says where each one belongs.
        direction is "client" or "server".
        """
        if direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}, got {direction!r}")
        method, request_id = parse_fields(raw)
        with self._db:
            self._db.execute(
                "INSERT INTO messages (seq, direction, raw, method, id_json) VALUES (?, ?, ?, ?, ?)",
                (seq, direction, bytes(raw), method, _id_json(request_id)),
            )
        return Entry(seq, direction, bytes(raw), method, request_id)

    def entries(self) -> list[Entry]:
        """Every entry, in seq order."""
        rows = self._db.execute(
            "SELECT seq, direction, raw, method, id_json FROM messages ORDER BY seq"
        )
        return [_to_entry(row) for row in rows]

    def with_id(self, value: Any) -> list[Entry]:
        """Entries whose id is exactly value (7 and "7" are different ids), in seq order.

        A message without an id never matches.
        """
        rows = self._db.execute(
            "SELECT seq, direction, raw, method, id_json FROM messages"
            " WHERE id_json = ? ORDER BY seq",
            (json.dumps(value, sort_keys=True),),
        )
        return [_to_entry(row) for row in rows]

    def close(self) -> None:
        self._db.close()


def _to_entry(row: tuple) -> Entry:
    seq, direction, raw, method, id_json = row
    return Entry(seq, direction, bytes(raw), method, NO_ID if id_json is None else json.loads(id_json))
