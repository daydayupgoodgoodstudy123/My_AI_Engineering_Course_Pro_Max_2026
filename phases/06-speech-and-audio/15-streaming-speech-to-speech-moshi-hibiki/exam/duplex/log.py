"""The session log: both sides of every frame of every duplex session, in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    """One 80 ms frame of a session."""

    index: int
    user: list[int]  # the user's codes, codebook 0 first
    model: list[int]  # the model's codes, codebook 0 first
    text: int  # the model's inner-monologue token for this frame


class SessionLog:
    """Frames of duplex sessions, as the training and replay tools read them back.

    The uplink task logs the user's side of a frame and the generation loop logs the model's
    side, each as soon as it has it, so the two sides of a frame arrive separately and in any
    order. Each side carries exactly CODEBOOKS codes in 0..CODEBOOK_SIZE - 1, so a frame missing
    a codebook is rejected, and each side of a frame is logged once. Text tokens are ints >= 0.
    Anything else raises ValueError.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def add_user(self, session: str, index: int, codes: list[int]) -> None:
        """Log the user's side of frame `index`."""
        raise NotImplementedError

    def add_model(self, session: str, index: int, text: int, codes: list[int]) -> None:
        """Log the model's side of frame `index`: its text token and its codes."""
        raise NotImplementedError

    def frame(self, session: str, index: int) -> Frame:
        """One frame. KeyError unless both of its sides are logged."""
        raise NotImplementedError

    def frames(self, session: str) -> list[Frame]:
        """Every frame of the session with both sides logged, in frame order."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
