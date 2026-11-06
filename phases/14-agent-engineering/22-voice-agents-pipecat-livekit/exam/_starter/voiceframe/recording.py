"""Call recordings: every frame that crossed the pipeline, kept for latency and barge-in reviews.

A recording is a binary file that is only ever appended to. It starts with MAGIC;
each record after it is written in one piece. If the process dies in the middle of
a write, the file ends with part of a record.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .frames import DOWNSTREAM, UPSTREAM

MAGIC = b"VFRAME1\n"


@dataclass(frozen=True)
class Record:
    t_ns: int  # call clock, in integer nanoseconds
    direction: str  # DOWNSTREAM or UPSTREAM
    kind: str  # frame kind, ASCII
    payload: bytes  # exactly what the frame carried: PCM audio, UTF-8 text, ...


class Recorder:
    """Appends records to a call recording.

    Opening a path that does not exist yet starts a new recording. Opening an
    existing recording continues it: if it ends with part of a record, that part is
    cut off first, so new records follow the last whole one.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        raise NotImplementedError

    def write(self, record: Record) -> None:
        """Append one record. It is in the file when write returns.

        Raises ValueError for a direction other than DOWNSTREAM or UPSTREAM, a
        timestamp that is not an int in [0, 2**63), a kind that is empty, not ASCII
        or longer than 255 characters, or a payload that is not bytes.
        """
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


def read_recording(path: str | os.PathLike) -> list[Record]:
    """Every whole record, in the order written. Part of a record at the end is left out.

    A file that does not start with MAGIC raises ValueError.
    """
    raise NotImplementedError
