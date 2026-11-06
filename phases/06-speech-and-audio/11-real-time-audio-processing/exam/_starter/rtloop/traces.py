"""Latency marks for every turn of every session, kept in SQLite."""
from __future__ import annotations

import sqlite3

STAGES = ("speech_end", "transcript", "first_token", "first_audio")


class TraceStore:
    """Per-turn latency marks of a voice agent.

    A mark is a reading of one monotonic clock in integer nanoseconds, taken when a stage of
    the turn happened: the user stopped talking (speech_end), the final transcript came in,
    the LLM produced its first token, the first reply audio played. Marks are stored and
    returned exactly as given.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def record(self, session: str, marks: dict[str, int]) -> int:
        """Store one turn and return its number within the session: 1, 2, ...

        marks maps names from STAGES to clock readings. A turn the user cut off stops early,
        but the stages it has start at speech_end, follow STAGES in order and never go back
        in time. Anything else raises ValueError.
        """
        raise NotImplementedError

    def turn(self, session: str, number: int) -> dict[str, int]:
        """The marks of one turn. Unknown turns raise KeyError."""
        raise NotImplementedError

    def slow_turns(self, budget_ns: int) -> list[tuple[str, int]]:
        """(session, number) of every turn whose first audio played more than budget_ns after
        speech_end, in the order the turns were recorded."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
