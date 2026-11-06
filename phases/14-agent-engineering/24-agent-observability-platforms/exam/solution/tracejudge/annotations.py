"""An annotation queue: traces waiting for human review, and the labels people give them."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS annotations (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL REFERENCES queue (trace_id),
    annotator TEXT NOT NULL,
    label TEXT NOT NULL,
    score REAL,
    note TEXT NOT NULL,
    created_ns INTEGER NOT NULL
);
"""


@dataclass(frozen=True)
class Annotation:
    trace_id: str
    annotator: str
    label: str
    score: float | None
    note: str
    created_ns: int


class AnnotationQueue:
    """Traces queued for review and their annotations, stored in SQLite."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.executescript(SCHEMA)

    def enqueue(self, trace_id: str) -> None:
        """Queue a trace for review. A trace that is already queued keeps its place."""
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO queue (trace_id) VALUES (?)", (trace_id,))

    def annotate(
        self,
        trace_id: str,
        annotator: str,
        label: str,
        score: float | None,
        note: str,
        created_ns: int,
    ) -> Annotation:
        """Record one person's annotation of a queued trace and return it.

        score is None (no score given) or a number from 0.0 to 1.0. note is kept
        exactly as written. created_ns is the annotator's clock in nanoseconds.
        Every annotation is kept, including a second one by the same person.
        A trace that was never queued raises KeyError; a score outside 0..1 raises ValueError.
        """
        if score is not None and not 0.0 <= score <= 1.0:
            raise ValueError(f"score must be None or between 0 and 1, got {score!r}")
        queued = self._db.execute("SELECT 1 FROM queue WHERE trace_id = ?", (trace_id,)).fetchone()
        if queued is None:
            raise KeyError(trace_id)
        annotation = Annotation(trace_id, annotator, label, score, note, created_ns)
        with self._db:
            self._db.execute(
                "INSERT INTO annotations (trace_id, annotator, label, score, note, created_ns)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (trace_id, annotator, label, score, note, created_ns),
            )
        return annotation

    def annotations(self, trace_id: str) -> list[Annotation]:
        """A trace's annotations in the order they were recorded."""
        rows = self._db.execute(
            "SELECT trace_id, annotator, label, score, note, created_ns FROM annotations"
            " WHERE trace_id = ? ORDER BY seq",
            (trace_id,),
        )
        return [Annotation(*row) for row in rows]

    def pending(self) -> list[str]:
        """Queued traces that nobody has annotated yet, in queue order."""
        rows = self._db.execute(
            "SELECT trace_id FROM queue WHERE trace_id NOT IN"
            " (SELECT trace_id FROM annotations) ORDER BY seq"
        )
        return [trace_id for (trace_id,) in rows]

    def close(self) -> None:
        self._db.close()
