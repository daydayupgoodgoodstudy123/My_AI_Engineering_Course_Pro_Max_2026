"""A labeled bank of clip features, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass

SPLITS = ("train", "eval")

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    split TEXT NOT NULL,
    sample_rate INTEGER NOT NULL,
    features TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Clip:
    clip_id: str
    label: str
    split: str
    sample_rate: int
    features: list[float]


class ClipBank:
    """Labeled clips and their pooled features.

    Every clip in one bank shares a sample rate and a feature size.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def add(self, label: str, split: str, sample_rate: int, features: list[float]) -> str:
        """Store one clip and return its new id. split is "train" or "eval"."""
        if split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
        first = self._db.execute(
            "SELECT sample_rate, features FROM clips ORDER BY seq LIMIT 1"
        ).fetchone()
        if first is not None:
            if sample_rate != first[0]:
                raise ValueError(f"bank holds {first[0]} Hz clips, got {sample_rate} Hz")
            if len(features) != len(json.loads(first[1])):
                raise ValueError("feature size differs from the clips already in the bank")
        clip_id = str(uuid.uuid4())
        with self._db:
            self._db.execute(
                "INSERT INTO clips (clip_id, label, split, sample_rate, features)"
                " VALUES (?, ?, ?, ?, ?)",
                (clip_id, label, split, sample_rate, json.dumps(list(features))),
            )
        return clip_id

    def get(self, clip_id: str) -> Clip:
        """Return a stored clip. Unknown ids raise KeyError."""
        row = self._db.execute(
            "SELECT clip_id, label, split, sample_rate, features FROM clips WHERE clip_id = ?",
            (clip_id,),
        ).fetchone()
        if row is None:
            raise KeyError(clip_id)
        return _to_clip(row)

    def clips(self, split: str | None = None) -> list[Clip]:
        """Stored clips in insertion order, optionally from one split only."""
        query = "SELECT clip_id, label, split, sample_rate, features FROM clips"
        params: tuple = ()
        if split is not None:
            query += " WHERE split = ?"
            params = (split,)
        return [_to_clip(row) for row in self._db.execute(query + " ORDER BY seq", params)]

    def close(self) -> None:
        self._db.close()


def _to_clip(row: tuple) -> Clip:
    clip_id, label, split, sample_rate, features = row
    return Clip(clip_id, label, split, sample_rate, json.loads(features))
