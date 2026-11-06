"""Generated tracks in SQLite: notes on the tick grid, the tempo map, and the generation record."""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from dataclasses import astuple, dataclass

from .compose import Note

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    ppq INTEGER NOT NULL,
    tempo TEXT NOT NULL,
    notes TEXT NOT NULL,
    meta TEXT NOT NULL
)
"""


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
        total = 0.0
        ends = [at for at, _ in self.tempo[1:]] + [math.inf]
        for (at, bpm), end in zip(self.tempo, ends):
            if tick <= at:
                break
            total += (min(tick, end) - at) * 60 / (bpm * self.ppq)
        return total


class TrackStore:
    """Tracks in a SQLite file. A stored track comes back exactly as it was added."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def add(self, track: Track) -> str:
        """Store a track and return its new id.

        Raise ValueError unless the tempo map starts at tick 0 with increasing ticks and
        positive tempos, and meta marks the track as AI-generated (the lesson's disclosure rule).
        """
        ticks = [at for at, _ in track.tempo]
        if not ticks or ticks[0] != 0 or any(a >= b for a, b in zip(ticks, ticks[1:])):
            raise ValueError("the tempo map must start at tick 0 and move forward")
        if any(bpm <= 0 for _, bpm in track.tempo):
            raise ValueError("tempos must be positive")
        if track.meta.get("ai_generated") is not True:
            raise ValueError("a generated track must be marked ai_generated")
        track_id = str(uuid.uuid4())
        with self._db:
            self._db.execute(
                "INSERT INTO tracks (track_id, title, ppq, tempo, notes, meta) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    track_id,
                    track.title,
                    track.ppq,
                    json.dumps(track.tempo),
                    json.dumps([astuple(note) for note in track.notes]),
                    json.dumps(track.meta),
                ),
            )
        return track_id

    def get(self, track_id: str) -> Track:
        """Return a stored track. Unknown ids raise KeyError."""
        row = self._db.execute(
            "SELECT title, ppq, tempo, notes, meta FROM tracks WHERE track_id = ?", (track_id,)
        ).fetchone()
        if row is None:
            raise KeyError(track_id)
        title, ppq, tempo, notes, meta = row
        return Track(
            title,
            ppq,
            [tuple(change) for change in json.loads(tempo)],
            [Note(*fields) for fields in json.loads(notes)],
            json.loads(meta),
        )

    def ids(self) -> list[str]:
        """Ids of the stored tracks, in the order they were added."""
        return [row[0] for row in self._db.execute("SELECT track_id FROM tracks ORDER BY seq")]

    def close(self) -> None:
        self._db.close()
