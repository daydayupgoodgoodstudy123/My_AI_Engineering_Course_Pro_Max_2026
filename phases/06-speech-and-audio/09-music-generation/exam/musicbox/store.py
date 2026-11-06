"""Generated tracks in SQLite: notes on the tick grid, the tempo map, and the generation record."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .compose import Note


@dataclass(frozen=True)
class Track:
    """A generated track.

    ppq is the number of ticks per quarter note, i.e. per beat. tempo is the tempo map: (tick,
    bpm) changes in tick order, the first at tick 0; each tempo holds from its tick until the
    next change. meta is the generation record (model, prompt, seed, ...).
    """

    title: str
    ppq: int
    tempo: list[tuple[int, float]]
    notes: list[Note]
    meta: dict

    def seconds(self, tick: int) -> float:
        """Wall-clock seconds from the start to tick, through every tempo change before it."""
        raise NotImplementedError


class TrackStore:
    """Tracks in a SQLite file. A stored track comes back exactly as it was added."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def add(self, track: Track) -> str:
        """Store a track and return its new id.

        Raise ValueError unless the tempo map starts at tick 0 with increasing ticks and
        positive tempos, and meta marks the track as AI-generated (the lesson's disclosure rule).
        """
        raise NotImplementedError

    def get(self, track_id: str) -> Track:
        """Return a stored track. Unknown ids raise KeyError."""
        raise NotImplementedError

    def ids(self) -> list[str]:
        """Ids of the stored tracks, in the order they were added."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
