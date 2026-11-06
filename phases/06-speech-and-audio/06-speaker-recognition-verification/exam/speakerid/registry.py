"""Enrolled speakers and their voiceprint templates, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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
        # TODO: create the schema

    def enroll(self, speaker: str, embedding: list[float]) -> str:
        """Store one enrollment embedding as given and return its new id.

        A zero vector raises ValueError (it has no direction to average), and so does an
        embedding whose dimension differs from the ones already stored.
        """
        raise NotImplementedError

    def remove(self, enrollment_id: str) -> None:
        """Delete one enrollment. Unknown ids raise KeyError."""
        raise NotImplementedError

    def enrollments(self, speaker: str) -> list[Enrollment]:
        """A speaker's enrollments, in the order they were added."""
        raise NotImplementedError

    def speakers(self) -> list[str]:
        """Names of the speakers with at least one enrollment, sorted."""
        raise NotImplementedError

    def template(self, speaker: str) -> list[float]:
        """The speaker's template, a unit vector. Speakers with no enrollments raise KeyError."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
