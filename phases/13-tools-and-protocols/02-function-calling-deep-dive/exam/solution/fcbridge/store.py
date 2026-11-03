"""Canonical conversations, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from .canonical import PROVIDERS, AssistantTurn, Call, ToolResult, Turn, UserTurn

SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    conversation_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (conversation_id, position)
)
"""

KINDS = {"user": UserTurn, "assistant": AssistantTurn, "tool": ToolResult}


class ConversationStore:
    """Conversations of canonical turns.

    Turns come back exactly as they were stored: OpenAI's arguments text byte for byte, the argument
    objects of Anthropic and Gemini as objects, ids as the providers wrote them, and the same JSON
    types throughout (an is_error flag is still a bool).
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def append(self, conversation_id: str, turn: Turn) -> int:
        """Add a turn at the end of a conversation and return its position: 0, 1, 2, ... per conversation.

        An assistant turn's provider must be one of PROVIDERS; anything else raises ValueError.
        """
        kind, body = _encode(turn)
        with self._db:
            (position,) = self._db.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM turns WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            self._db.execute(
                "INSERT INTO turns (conversation_id, position, kind, body) VALUES (?, ?, ?, ?)",
                (conversation_id, position, kind, body),
            )
        return position

    def replace(self, conversation_id: str, position: int, turn: Turn) -> None:
        """Put a new turn in place of the one at position, for example to redact a tool result.

        The new turn keeps the old one's place in the conversation. An unknown position raises KeyError.
        """
        kind, body = _encode(turn)
        with self._db:
            cursor = self._db.execute(
                "UPDATE turns SET kind = ?, body = ? WHERE conversation_id = ? AND position = ?",
                (kind, body, conversation_id, position),
            )
        if cursor.rowcount == 0:
            raise KeyError((conversation_id, position))

    def turns(self, conversation_id: str) -> list[Turn]:
        """The conversation's turns in order; [] for an unknown conversation."""
        rows = self._db.execute(
            "SELECT kind, body FROM turns WHERE conversation_id = ? ORDER BY position",
            (conversation_id,),
        )
        return [_decode(kind, body) for kind, body in rows]

    def close(self) -> None:
        self._db.close()


def _encode(turn: Turn) -> tuple[str, str]:
    if isinstance(turn, AssistantTurn) and turn.provider not in PROVIDERS:
        raise ValueError(f"unknown provider {turn.provider!r}; expected one of {', '.join(PROVIDERS)}")
    for kind, cls in KINDS.items():
        if type(turn) is cls:
            # The whole turn as one JSON document: OpenAI's arguments text is a JSON string inside it,
            # so it comes back character for character, and JSON keeps true apart from 1.
            return kind, json.dumps(asdict(turn), ensure_ascii=False)
    raise TypeError(f"not a turn: {turn!r}")


def _decode(kind: str, body: str) -> Turn:
    fields = json.loads(body)
    if kind == "assistant":
        fields["calls"] = [Call(**call) for call in fields["calls"]]
    return KINDS[kind](**fields)
