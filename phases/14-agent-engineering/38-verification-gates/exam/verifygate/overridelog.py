"""outputs/verification/overrides.jsonl, the gate's override audit log."""
from __future__ import annotations

import json
from pathlib import Path

from .signing import FIELDS, verify_signature


class LogTampered(Exception):
    """A line of the override log that is not a complete, correctly signed entry."""

    def __init__(self, line: int, reason: str) -> None:
        super().__init__(f"override log line {line}: {reason}")
        self.line = line
        self.reason = reason


class OverrideLog:
    """The signed override log: one entry per line, appended, never rewritten.

    The file is git-tracked, so every override shows up in review, and the gate reads it back on
    every run. An entry is exactly the six signing.FIELDS plus a "signature" that verifies under the
    log's secret (see signing.py). Each line is json.dumps(entry) followed by a newline. A log opened
    without a secret raises ValueError: no secret, no overrides (fail closed).
    """

    def __init__(self, path: str | Path, secret: bytes) -> None:
        self.path = Path(path)
        self.secret = secret

    def append(self, entry: dict) -> int:
        """Append one signed entry and return its line number, counting from 1.

        The entry is written as it is. An entry with other fields than the six and the signature, or
        whose signature does not verify, raises ValueError and nothing is written. The file and its
        directory are created on the first append.
        """
        raise NotImplementedError

    def entries(self) -> list[dict]:
        """Every entry, in file order, exactly as it was appended. A log that does not exist is empty.

        The signature covers the entry's fields, not how its line is spelled, so a line written by
        another tool with other spacing, key order or raw UTF-8 still reads. A line that is not one
        complete entry with a valid signature raises LogTampered with its line number, counting from
        1: a changed, added or missing field, a cut-off or blank line, or a field given twice, which
        two JSON readers could resolve to different values.
        """
        raise NotImplementedError
