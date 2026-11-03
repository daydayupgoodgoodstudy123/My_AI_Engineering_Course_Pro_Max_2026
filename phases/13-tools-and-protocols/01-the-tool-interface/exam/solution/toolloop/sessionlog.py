"""The conversation history, kept as an append-only JSON Lines file."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path


class SessionLog:
    """The history of one conversation, one message per line, appended as it happens.

    A line is one message as a JSON object, in UTF-8 with non-ASCII characters written
    as they are (people read these logs with tail and grep), ending in "\\n". Messages
    must be standard JSON, which has no NaN or infinity: anything else raises ValueError
    and nothing is written.

    Every append is in the file by the time append returns, so a crash loses at most the
    line being written. Opening a log whose last line has no newline (a crash cut that
    write short) drops that line and carries on: the messages before it are kept, and
    later appends read back as usual. Any other unreadable line means the file is
    corrupt, and opening it raises ValueError.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        """Open the log at path, creating the file if needed."""
        self.path = Path(path)
        data = self.path.read_bytes() if self.path.exists() else b""
        end = data.rfind(b"\n") + 1  # a line counts once its newline is on disk
        self._messages: list[dict] = []
        for number, line in enumerate(data[:end].split(b"\n")[:-1], start=1):
            try:
                self._messages.append(json.loads(line.decode("utf-8")))
            except ValueError as exc:  # bad UTF-8 or bad JSON
                raise ValueError(f"{self.path}: line {number} is corrupt") from exc
        if end < len(data):
            os.truncate(self.path, end)  # drop the torn write, so the next line starts clean
        self._file = open(self.path, "ab")

    def append(self, message: dict) -> None:
        """Add one message at the end of the log."""
        line = json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n"
        self._file.write(line.encode("utf-8"))
        self._file.flush()
        self._messages.append(json.loads(line))

    def messages(self) -> list[dict]:
        """Every message in the log, in the order appended, exactly as appended."""
        return copy.deepcopy(self._messages)

    def close(self) -> None:
        self._file.close()
