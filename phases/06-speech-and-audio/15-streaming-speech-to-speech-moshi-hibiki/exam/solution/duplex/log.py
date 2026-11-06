"""The session log: both sides of every frame of every duplex session, in SQLite."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .tokens import CODEBOOK_SIZE, CODEBOOKS

SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
    session TEXT NOT NULL,
    frame INTEGER NOT NULL,
    user TEXT,
    model TEXT,
    text INTEGER,
    PRIMARY KEY (session, frame)
)
"""

COMPLETE = "user IS NOT NULL AND model IS NOT NULL"


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
        with self._db:
            self._db.execute(SCHEMA)

    def add_user(self, session: str, index: int, codes: list[int]) -> None:
        """Log the user's side of frame `index`."""
        user = _codes(codes)
        with self._db:
            self._check_new(session, index, "user")
            self._db.execute(
                "INSERT INTO frames (session, frame, user) VALUES (?, ?, ?)"
                " ON CONFLICT (session, frame) DO UPDATE SET user = excluded.user",
                (session, index, user),
            )

    def add_model(self, session: str, index: int, text: int, codes: list[int]) -> None:
        """Log the model's side of frame `index`: its text token and its codes."""
        model = _codes(codes)
        if not _is_token(text):
            raise ValueError(f"a text token is an int >= 0, got {text!r}")
        with self._db:
            self._check_new(session, index, "model")
            self._db.execute(
                "INSERT INTO frames (session, frame, model, text) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (session, frame) DO UPDATE SET model = excluded.model, text = excluded.text",
                (session, index, model, text),
            )

    def frame(self, session: str, index: int) -> Frame:
        """One frame. KeyError unless both of its sides are logged."""
        row = self._db.execute(
            f"SELECT frame, user, model, text FROM frames"
            f" WHERE session = ? AND frame = ? AND {COMPLETE}",
            (session, index),
        ).fetchone()
        if row is None:
            raise KeyError((session, index))
        return _to_frame(row)

    def frames(self, session: str) -> list[Frame]:
        """Every frame of the session with both sides logged, in frame order."""
        rows = self._db.execute(
            f"SELECT frame, user, model, text FROM frames"
            f" WHERE session = ? AND {COMPLETE} ORDER BY frame",
            (session,),
        )
        return [_to_frame(row) for row in rows]

    def close(self) -> None:
        self._db.close()

    def _check_new(self, session: str, index: int, side: str) -> None:
        if not _is_token(index):
            raise ValueError(f"a frame index is an int >= 0, got {index!r}")
        row = self._db.execute(
            f"SELECT {side} FROM frames WHERE session = ? AND frame = ?", (session, index)
        ).fetchone()
        if row is not None and row[0] is not None:
            raise ValueError(f"the {side} side of frame {index} of {session!r} is already logged")


def _is_token(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _codes(codes: list[int]) -> str:
    if len(codes) != CODEBOOKS:
        raise ValueError(f"a frame carries {CODEBOOKS} codes, got {len(codes)}")
    if not all(_is_token(code) and code < CODEBOOK_SIZE for code in codes):
        raise ValueError(f"codes are ints in 0..{CODEBOOK_SIZE - 1}, got {codes!r}")
    return json.dumps(list(codes))


def _to_frame(row: tuple) -> Frame:
    index, user, model, text = row
    return Frame(index, json.loads(user), json.loads(model), text)
