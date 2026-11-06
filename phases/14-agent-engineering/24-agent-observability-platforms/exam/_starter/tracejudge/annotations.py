"""An annotation queue: traces waiting for human review, and the labels people give them."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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
        # TODO: create the schema

    def enqueue(self, trace_id: str) -> None:
        """Queue a trace for review. A trace that is already queued keeps its place."""
        raise NotImplementedError

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
        raise NotImplementedError

    def annotations(self, trace_id: str) -> list[Annotation]:
        """A trace's annotations in the order they were recorded."""
        raise NotImplementedError

    def pending(self) -> list[str]:
        """Queued traces that nobody has annotated yet, in queue order."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
