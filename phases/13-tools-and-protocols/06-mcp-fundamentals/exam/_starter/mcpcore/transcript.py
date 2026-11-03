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


class Transcript:
    """Every message of a session, in seq order, exactly as it was sent."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def record(self, seq: int, direction: str, raw: bytes) -> Entry:
        """Store one line as it crossed the wire and return its entry.

        Messages may be recorded in any order; seq says where each one belongs.
        direction is "client" or "server".
        """
        raise NotImplementedError

    def entries(self) -> list[Entry]:
        """Every entry, in seq order."""
        raise NotImplementedError

    def with_id(self, value: Any) -> list[Entry]:
        """Entries whose id is exactly value (7 and "7" are different ids), in seq order.

        A message without an id never matches.
        """
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
