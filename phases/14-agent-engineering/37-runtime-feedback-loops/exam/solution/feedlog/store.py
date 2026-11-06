"""The feedback log: JSONL, one record per line, rotated by size."""
from __future__ import annotations

import os
from pathlib import Path

from .record import FeedbackRecord

MAX_BYTES = 1024 * 1024
KEEP = 5


class FeedbackLog:
    """Feedback records in path, plus the rotated files path.1 (newest) to path.<keep> (oldest).

    - A record is written as record.to_json() and "\\n", in UTF-8.
    - No file grows past max_bytes. When the next record would take path past max_bytes, path is
      rotated first: path.<keep> is deleted, each path.<i> becomes path.<i + 1>, path becomes
      path.1, and the record starts a new path. A record larger than max_bytes on its own gets a
      file to itself. A record is never split between files.
    - A FeedbackLog opened on an existing log carries on where the last one stopped.
    - keep is at least 1.
    """

    def __init__(self, path: str | os.PathLike[str], max_bytes: int = MAX_BYTES, keep: int = KEEP) -> None:
        if keep < 1:
            raise ValueError(f"keep must be at least 1, got {keep}")
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.keep = keep

    def append(self, record: FeedbackRecord) -> None:
        """Write one record, rotating first if it would not fit in path."""
        line = (record.to_json() + "\n").encode("utf-8")
        size = self.path.stat().st_size if self.path.exists() else 0
        if size and size + len(line) > self.max_bytes:
            self._rotate()
        with open(self.path, "ab") as fh:
            fh.write(line)

    def current(self) -> list[FeedbackRecord]:
        """The records in path, oldest first: what the agent's loop reads at every turn."""
        return _read(self.path)

    def load_all(self) -> list[FeedbackRecord]:
        """Every record the log still holds, path.<keep> first and path last, each file oldest first.

        This is what CI and reviewers read. Other files next to the log are not part of it.
        """
        records: list[FeedbackRecord] = []
        for i in range(self.keep, 0, -1):
            records.extend(_read(self._rotated(i)))
        records.extend(_read(self.path))
        return records

    def _rotated(self, i: int) -> Path:
        return self.path.with_name(f"{self.path.name}.{i}")

    def _rotate(self) -> None:
        self._rotated(self.keep).unlink(missing_ok=True)
        for i in range(self.keep - 1, 0, -1):
            if self._rotated(i).exists():
                self._rotated(i).replace(self._rotated(i + 1))
        self.path.replace(self._rotated(1))


def _read(path: Path) -> list[FeedbackRecord]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return []
    return [FeedbackRecord.from_json(line) for line in data.decode("utf-8").split("\n") if line]
