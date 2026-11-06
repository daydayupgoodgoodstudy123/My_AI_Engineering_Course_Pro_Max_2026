"""An append-only audit log of spoof-detection decisions, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Entry:
    entry_id: int
    clip: str
    model: str
    threshold: float
    score: float
    verdict: str
    at: datetime


class AuditLog:
    """Every spoof-detection decision, exactly as it was made.

    An auditor must be able to re-derive each verdict later from the stored score and threshold,
    so both come back exactly as given. Times must be timezone-aware and come back in UTC.
    Ids are 1, 2, 3, ... in the order decisions are recorded.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def record(self, clip: str, model: str, threshold: float, score: float, at: datetime) -> Entry:
        """Log one decision made by model about clip, and return it.

        The verdict is "spoof" when the score is at or above the threshold, else "bonafide".
        A NaN score or threshold raises ValueError (NaN compares false with everything, so the
        clip would pass as bona fide). A naive at raises ValueError.
        """
        raise NotImplementedError

    def get(self, entry_id: int) -> Entry:
        """The logged decision. Unknown ids raise KeyError."""
        raise NotImplementedError

    def entries(self, model: str | None = None) -> list[Entry]:
        """Logged decisions in the order they were recorded, optionally by one model only."""
        raise NotImplementedError

    def flips(self, model: str, threshold: float) -> list[Entry]:
        """model's logged decisions whose verdict would change under a new threshold, in order."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
