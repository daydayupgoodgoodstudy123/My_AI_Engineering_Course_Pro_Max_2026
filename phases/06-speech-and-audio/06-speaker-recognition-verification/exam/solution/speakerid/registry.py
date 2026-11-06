"""Enrolled speakers and their voiceprint templates, stored in SQLite."""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from dataclasses import dataclass

from .embed import l2_normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS enrollments (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id TEXT NOT NULL UNIQUE,
    speaker TEXT NOT NULL,
    embedding TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Enrollment:
    enrollment_id: str
    speaker: str
    embedding: list[float]


class SpeakerRegistry:
    """Enrollment embeddings, several per speaker, and the template built from them.

    A speaker's template is the mean of their enrollment embeddings, each scaled to unit length
    first, and then scaled to unit length itself. It depends only on the enrollments the speaker
    holds now: removing an enrollment gives back exactly the template from before it was added.
    Every embedding in one registry has the same dimension.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def enroll(self, speaker: str, embedding: list[float]) -> str:
        """Store one enrollment embedding as given and return its new id.

        A zero vector raises ValueError (it has no direction to average), and so does an
        embedding whose dimension differs from the ones already stored.
        """
        if not any(embedding):
            raise ValueError("cannot enroll a zero embedding")
        first = self._db.execute(
            "SELECT embedding FROM enrollments ORDER BY seq LIMIT 1"
        ).fetchone()
        if first is not None and len(embedding) != len(json.loads(first[0])):
            raise ValueError("embedding dimension differs from the enrolled ones")
        enrollment_id = str(uuid.uuid4())
        with self._db:
            self._db.execute(
                "INSERT INTO enrollments (enrollment_id, speaker, embedding) VALUES (?, ?, ?)",
                (enrollment_id, speaker, json.dumps(list(embedding))),
            )
        return enrollment_id

    def remove(self, enrollment_id: str) -> None:
        """Delete one enrollment. Unknown ids raise KeyError."""
        with self._db:
            deleted = self._db.execute(
                "DELETE FROM enrollments WHERE enrollment_id = ?", (enrollment_id,)
            ).rowcount
        if deleted == 0:
            raise KeyError(enrollment_id)

    def enrollments(self, speaker: str) -> list[Enrollment]:
        """A speaker's enrollments, in the order they were added."""
        rows = self._db.execute(
            "SELECT enrollment_id, speaker, embedding FROM enrollments"
            " WHERE speaker = ? ORDER BY seq",
            (speaker,),
        )
        return [Enrollment(eid, spk, json.loads(emb)) for eid, spk, emb in rows]

    def speakers(self) -> list[str]:
        """Names of the speakers with at least one enrollment, sorted."""
        rows = self._db.execute("SELECT DISTINCT speaker FROM enrollments ORDER BY speaker")
        return [name for (name,) in rows]

    def template(self, speaker: str) -> list[float]:
        """The speaker's template, a unit vector. Speakers with no enrollments raise KeyError."""
        units = [l2_normalize(e.embedding) for e in self.enrollments(speaker)]
        if not units:
            raise KeyError(speaker)
        return l2_normalize([math.fsum(column) / len(units) for column in zip(*units)])

    def close(self) -> None:
        self._db.close()
