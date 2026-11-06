"""An append-only audit log of spoof-detection decisions, stored in SQLite."""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    clip TEXT NOT NULL,
    model TEXT NOT NULL,
    threshold REAL NOT NULL,
    score REAL NOT NULL,
    verdict TEXT NOT NULL,
    at TEXT NOT NULL
)
"""
COLUMNS = "entry_id, clip, model, threshold, score, verdict, at"


@dataclass(frozen=True)
class Entry:
    entry_id: int
    clip: str
    model: str
    threshold: float
    score: float
    verdict: str
    at: datetime


def decide(score: float, threshold: float) -> str:
    return "spoof" if score >= threshold else "bonafide"


class AuditLog:
    """Every spoof-detection decision, exactly as it was made.

    An auditor must be able to re-derive each verdict later from the stored score and threshold,
    so both come back exactly as given. Times must be timezone-aware and come back in UTC.
    Ids are 1, 2, 3, ... in the order decisions are recorded.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def record(self, clip: str, model: str, threshold: float, score: float, at: datetime) -> Entry:
        """Log one decision made by model about clip, and return it.

        The verdict is "spoof" when the score is at or above the threshold, else "bonafide".
        A NaN score or threshold raises ValueError (NaN compares false with everything, so the
        clip would pass as bona fide). A naive at raises ValueError.
        """
        if math.isnan(score) or math.isnan(threshold):
            raise ValueError("score and threshold must be numbers, not NaN")
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError(f"{at.isoformat()} has no time zone")
        when = at.astimezone(timezone.utc).isoformat()
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO decisions (clip, model, threshold, score, verdict, at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (clip, model, threshold, score, decide(score, threshold), when),
            )
        return self.get(cursor.lastrowid)

    def get(self, entry_id: int) -> Entry:
        """The logged decision. Unknown ids raise KeyError."""
        row = self._db.execute(
            f"SELECT {COLUMNS} FROM decisions WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            raise KeyError(entry_id)
        return _to_entry(row)

    def entries(self, model: str | None = None) -> list[Entry]:
        """Logged decisions in the order they were recorded, optionally by one model only."""
        query = f"SELECT {COLUMNS} FROM decisions"
        params: tuple = ()
        if model is not None:
            query += " WHERE model = ?"
            params = (model,)
        return [_to_entry(row) for row in self._db.execute(query + " ORDER BY entry_id", params)]

    def flips(self, model: str, threshold: float) -> list[Entry]:
        """model's logged decisions whose verdict would change under a new threshold, in order."""
        return [e for e in self.entries(model) if decide(e.score, threshold) != e.verdict]

    def close(self) -> None:
        self._db.close()


def _to_entry(row: tuple) -> Entry:
    entry_id, clip, model, threshold, score, verdict, at = row
    return Entry(entry_id, clip, model, threshold, score, verdict, datetime.fromisoformat(at))
