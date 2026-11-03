"""The conversation history, kept as an append-only JSON Lines file."""
from __future__ import annotations

import os


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
        raise NotImplementedError

    def append(self, message: dict) -> None:
        """Add one message at the end of the log."""
        raise NotImplementedError

    def messages(self) -> list[dict]:
        """Every message in the log, in the order appended, exactly as appended."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
