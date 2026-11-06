"""A labeled bank of clip features, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

SPLITS = ("train", "eval")


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
        # TODO: create the schema

    def add(self, label: str, split: str, sample_rate: int, features: list[float]) -> str:
        """Store one clip and return its new id. split is "train" or "eval"."""
        raise NotImplementedError

    def get(self, clip_id: str) -> Clip:
        """Return a stored clip. Unknown ids raise KeyError."""
        raise NotImplementedError

    def clips(self, split: str | None = None) -> list[Clip]:
        """Stored clips in insertion order, optionally from one split only."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
