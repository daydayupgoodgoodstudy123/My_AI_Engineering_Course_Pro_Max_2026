"""outputs/verification/overrides.jsonl, the gate's override audit log."""
from __future__ import annotations

import json
from pathlib import Path

from .signing import FIELDS, verify_signature

_ENTRY_KEYS = frozenset(FIELDS) | {"signature"}


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
        if not secret:
            raise ValueError("no override secret: refusing to open the override log (fail closed)")
        self.path = Path(path)
        self.secret = secret

    def append(self, entry: dict) -> int:
        """Append one signed entry and return its line number, counting from 1.

        The entry is written as it is. An entry with other fields than the six and the signature, or
        whose signature does not verify, raises ValueError and nothing is written. The file and its
        directory are created on the first append.
        """
        problem = self._problem(entry)
        if problem:
            raise ValueError(f"refusing to append an override: {problem}")
        line = (json.dumps(entry) + "\n").encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+b") as fh:
            fh.seek(0)
            number = fh.read().count(b"\n") + 1
            fh.write(line)
        return number

    def entries(self) -> list[dict]:
        """Every entry, in file order, exactly as it was appended. A log that does not exist is empty.

        The signature covers the entry's fields, not how its line is spelled, so a line written by
        another tool with other spacing, key order or raw UTF-8 still reads. A line that is not one
        complete entry with a valid signature raises LogTampered with its line number, counting from
        1: a changed, added or missing field, a cut-off or blank line, or a field given twice, which
        two JSON readers could resolve to different values.
        """
        if not self.path.exists():
            return []
        lines = self.path.read_bytes().split(b"\n")
        if lines[-1] == b"":
            lines.pop()
        out: list[dict] = []
        for number, raw in enumerate(lines, start=1):
            entry, problem = _parse(raw)
            problem = problem or self._problem(entry)
            if problem:
                raise LogTampered(number, problem)
            out.append(entry)
        return out

    def _problem(self, entry: object) -> str | None:
        if not isinstance(entry, dict):
            return "not a JSON object"
        if set(entry) != _ENTRY_KEYS:
            return "fields are not the six override fields and a signature"
        if not verify_signature(entry, self.secret):
            return "signature does not verify"
        return None


class _RepeatedField(ValueError):
    pass


def _no_repeats(pairs: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise _RepeatedField
    return dict(pairs)


def _parse(raw: bytes) -> tuple[object, str | None]:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_repeats), None
    except _RepeatedField:
        return None, "a field is given twice"
    except ValueError:
        return None, "not one complete JSON entry"
