"""Call recordings: every frame that crossed the pipeline, kept for latency and barge-in reviews.

A recording is a binary file that is only ever appended to. It starts with MAGIC;
each record after it is written in one piece. If the process dies in the middle of
a write, the file ends with part of a record.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

from .frames import DOWNSTREAM, UPSTREAM

MAGIC = b"VFRAME1\n"

# t_ns, direction (0 downstream, 1 upstream), kind length, payload length
_HEADER = struct.Struct(">qBBI")
_DIRECTIONS = (DOWNSTREAM, UPSTREAM)


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
        self.path = Path(path)
        if self.path.exists() and self.path.stat().st_size > 0:
            data = self.path.read_bytes()
            if not data.startswith(MAGIC):
                raise ValueError(f"{self.path} is not a call recording")
            _, end = _parse(data)
            if end < len(data):
                os.truncate(self.path, end)
            self._file = open(self.path, "ab")
        else:
            self._file = open(self.path, "wb")
            self._file.write(MAGIC)
            self._file.flush()

    def write(self, record: Record) -> None:
        """Append one record. It is in the file when write returns.

        Raises ValueError for a direction other than DOWNSTREAM or UPSTREAM, a
        timestamp that is not an int in [0, 2**63), a kind that is empty, not ASCII
        or longer than 255 characters, or a payload that is not bytes.
        """
        if record.direction not in _DIRECTIONS:
            raise ValueError(f"bad direction {record.direction!r}")
        t_ns = record.t_ns
        if isinstance(t_ns, bool) or not isinstance(t_ns, int) or not 0 <= t_ns < 2**63:
            raise ValueError(f"t_ns must be an int in [0, 2**63), got {t_ns!r}")
        if not record.kind or not record.kind.isascii() or len(record.kind) > 255:
            raise ValueError(f"bad frame kind {record.kind!r}")
        if not isinstance(record.payload, bytes):
            raise ValueError("payload must be bytes")
        kind = record.kind.encode("ascii")
        header = _HEADER.pack(t_ns, _DIRECTIONS.index(record.direction), len(kind), len(record.payload))
        self._file.write(header + kind + record.payload)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def read_recording(path: str | os.PathLike) -> list[Record]:
    """Every whole record, in the order written. Part of a record at the end is left out.

    A file that does not start with MAGIC raises ValueError.
    """
    data = Path(path).read_bytes()
    if not data.startswith(MAGIC):
        raise ValueError(f"{path} is not a call recording")
    records, _ = _parse(data)
    return records


def _parse(data: bytes) -> tuple[list[Record], int]:
    """Whole records after MAGIC, and the offset where the last one ends."""
    records: list[Record] = []
    pos = len(MAGIC)
    while pos + _HEADER.size <= len(data):
        t_ns, direction, kind_len, payload_len = _HEADER.unpack_from(data, pos)
        start = pos + _HEADER.size
        end = start + kind_len + payload_len
        if end > len(data):
            break
        kind = data[start : start + kind_len]
        if direction >= len(_DIRECTIONS) or t_ns < 0 or not kind_len or not kind.isascii():
            raise ValueError(f"corrupt record at byte {pos}")
        records.append(Record(t_ns, _DIRECTIONS[direction], kind.decode("ascii"), data[start + kind_len : end]))
        pos = end
    return records, pos
