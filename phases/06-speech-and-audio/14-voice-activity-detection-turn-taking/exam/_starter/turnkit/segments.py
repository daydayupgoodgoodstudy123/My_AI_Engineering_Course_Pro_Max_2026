"""Speech segments per recording, kept in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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
        # TODO: create the schema

    def add(self, recording: str, sample_rate: int, start: int, end: int) -> Segment:
        """Store [start, end) and return the stored segment that now contains it.

        Raises ValueError unless 0 <= start < end, or when the recording already has
        another sample rate.
        """
        raise NotImplementedError

    def segments(self, recording: str) -> list[Segment]:
        """The recording's segments in time order."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
