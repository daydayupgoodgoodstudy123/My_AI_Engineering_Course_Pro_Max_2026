"""Latency marks for every turn of every session, kept in SQLite."""
from __future__ import annotations

import sqlite3

STAGES = ("speech_end", "transcript", "first_token", "first_audio")

SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    number INTEGER NOT NULL,
    speech_end INTEGER NOT NULL,
    transcript INTEGER,
    first_token INTEGER,
    first_audio INTEGER,
    UNIQUE (session, number)
)
"""


class TraceStore:
    """Per-turn latency marks of a voice agent.

    A mark is a reading of one monotonic clock in integer nanoseconds, taken when a stage of
    the turn happened: the user stopped talking (speech_end), the final transcript came in,
    the LLM produced its first token, the first reply audio played. Marks are stored and
    returned exactly as given.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def record(self, session: str, marks: dict[str, int]) -> int:
        """Store one turn and return its number within the session: 1, 2, ...

        marks maps names from STAGES to clock readings. A turn the user cut off stops early,
        but the stages it has start at speech_end, follow STAGES in order and never go back
        in time. Anything else raises ValueError.
        """
        _check(marks)
        (number,) = self._db.execute(
            "SELECT COUNT(*) + 1 FROM turns WHERE session = ?", (session,)
        ).fetchone()
        with self._db:
            self._db.execute(
                "INSERT INTO turns (session, number, speech_end, transcript, first_token,"
                " first_audio) VALUES (?, ?, ?, ?, ?, ?)",
                (session, number, *(marks.get(stage) for stage in STAGES)),
            )
        return number

    def turn(self, session: str, number: int) -> dict[str, int]:
        """The marks of one turn. Unknown turns raise KeyError."""
        row = self._db.execute(
            "SELECT speech_end, transcript, first_token, first_audio FROM turns"
            " WHERE session = ? AND number = ?",
            (session, number),
        ).fetchone()
        if row is None:
            raise KeyError((session, number))
        return {stage: value for stage, value in zip(STAGES, row) if value is not None}

    def slow_turns(self, budget_ns: int) -> list[tuple[str, int]]:
        """(session, number) of every turn whose first audio played more than budget_ns after
        speech_end, in the order the turns were recorded."""
        rows = self._db.execute(
            "SELECT session, number FROM turns WHERE first_audio - speech_end > ? ORDER BY seq",
            (budget_ns,),
        )
        return [(session, number) for session, number in rows]

    def close(self) -> None:
        self._db.close()


def _check(marks: dict[str, int]) -> None:
    unknown = sorted(set(marks) - set(STAGES))
    if unknown:
        raise ValueError(f"unknown stages: {unknown}")
    present = [stage for stage in STAGES if stage in marks]
    if not present or present != list(STAGES[: len(present)]):
        raise ValueError("a turn's marks start at speech_end and skip no stage")
    values = [marks[stage] for stage in present]
    if any(type(value) is not int for value in values):
        raise ValueError("marks are integer nanoseconds")
    if any(later < earlier for earlier, later in zip(values, values[1:])):
        raise ValueError("marks go back in time")
