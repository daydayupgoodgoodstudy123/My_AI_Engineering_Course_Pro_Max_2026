"""Speech segments per recording, kept in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS recordings ("
    " recording TEXT PRIMARY KEY, sample_rate INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS segments ("
    " recording TEXT NOT NULL REFERENCES recordings (recording),"
    " start_sample INTEGER NOT NULL, end_sample INTEGER NOT NULL)",
    "CREATE INDEX IF NOT EXISTS segments_by_start ON segments (recording, start_sample)",
)


@dataclass(frozen=True)
class Segment:
    recording: str
    sample_rate: int
    start: int
    end: int


class SegmentTable:
    """Speech segments per recording, as half-open sample ranges [start, end).

    Every recording has one sample rate, fixed by its first segment. A segment that overlaps
    or touches stored segments of the same recording is merged with them, so the segments of
    a recording never overlap or touch.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            for statement in SCHEMA:
                self._db.execute(statement)

    def add(self, recording: str, sample_rate: int, start: int, end: int) -> Segment:
        """Store [start, end) and return the stored segment that now contains it.

        Raises ValueError unless 0 <= start < end, or when the recording already has
        another sample rate.
        """
        if not 0 <= start < end:
            raise ValueError(f"need 0 <= start < end, got [{start}, {end})")
        row = self._db.execute(
            "SELECT sample_rate FROM recordings WHERE recording = ?", (recording,)
        ).fetchone()
        if row is not None and row[0] != sample_rate:
            raise ValueError(f"{recording!r} is stored at {row[0]} Hz, got {sample_rate} Hz")
        with self._db:
            if row is None:
                self._db.execute("INSERT INTO recordings VALUES (?, ?)", (recording, sample_rate))
            touching = self._db.execute(
                "SELECT rowid, start_sample, end_sample FROM segments"
                " WHERE recording = ? AND start_sample <= ? AND end_sample >= ?",
                (recording, end, start),
            ).fetchall()
            for rowid, first, last in touching:
                start, end = min(start, first), max(end, last)
                self._db.execute("DELETE FROM segments WHERE rowid = ?", (rowid,))
            self._db.execute(
                "INSERT INTO segments (recording, start_sample, end_sample) VALUES (?, ?, ?)",
                (recording, start, end),
            )
        return Segment(recording, sample_rate, start, end)

    def segments(self, recording: str) -> list[Segment]:
        """The recording's segments in time order."""
        row = self._db.execute(
            "SELECT sample_rate FROM recordings WHERE recording = ?", (recording,)
        ).fetchone()
        if row is None:
            return []
        rows = self._db.execute(
            "SELECT start_sample, end_sample FROM segments WHERE recording = ? ORDER BY start_sample",
            (recording,),
        )
        return [Segment(recording, row[0], start, end) for start, end in rows]

    def close(self) -> None:
        self._db.close()
