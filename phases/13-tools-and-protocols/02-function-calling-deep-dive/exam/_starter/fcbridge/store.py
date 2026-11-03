"""Canonical conversations, stored in SQLite."""
from __future__ import annotations

import sqlite3

from .canonical import Turn


class ConversationStore:
    """Conversations of canonical turns.

    Turns come back exactly as they were stored: OpenAI's arguments text byte for byte, the argument
    objects of Anthropic and Gemini as objects, ids as the providers wrote them, and the same JSON
    types throughout (an is_error flag is still a bool).
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def append(self, conversation_id: str, turn: Turn) -> int:
        """Add a turn at the end of a conversation and return its position: 0, 1, 2, ... per conversation.

        An assistant turn's provider must be one of PROVIDERS; anything else raises ValueError.
        """
        raise NotImplementedError

    def replace(self, conversation_id: str, position: int, turn: Turn) -> None:
        """Put a new turn in place of the one at position, for example to redact a tool result.

        The new turn keeps the old one's place in the conversation. An unknown position raises KeyError.
        """
        raise NotImplementedError

    def turns(self, conversation_id: str) -> list[Turn]:
        """The conversation's turns in order; [] for an unknown conversation."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
