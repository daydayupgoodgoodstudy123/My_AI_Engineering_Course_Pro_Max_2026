"""Transcripts: a run's message buffer saved as one JSON snapshot, and read back.

Long runs are debugged from their transcripts, and a run can go on from one, so a snapshot reads
back exactly: the same messages in the same order, every reasoning item byte for byte.

The layout is shared with the trace viewer:

    {"version": 1, "messages": [<message>, ...]}

Each message is its dataclass fields as dataclasses.asdict gives them, except that reasoning is
the item's standard base64 text, or null when the turn has none.
"""
from __future__ import annotations

import os

from .messages import Message

VERSION = 1


def save_transcript(path: str | os.PathLike, messages: list[Message]) -> None:
    """Write the snapshot, replacing any earlier one at path.

    The whole file is replaced at once: a reader has either the old snapshot or the new one, and a
    save that fails, for example on a tool result JSON cannot hold, leaves the old one in place.
    """
    raise NotImplementedError


def load_transcript(path: str | os.PathLike) -> list[Message]:
    """Read a snapshot back into messages equal to the ones saved."""
    raise NotImplementedError
