"""The refine history on disk: round 0 in full, then one line diff per round."""
from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Revision:
    number: int  # the round, from 0
    output: str
    critique: str


class CorruptChain(ValueError):
    """A stored round does not rebuild to what was appended."""


class RevisionChain:
    """Every round's output and critique, kept as a chain of line diffs in one file.

    The file is UTF-8 text a reviewer can read. It holds the first round's output in full and, for
    every later round, only the lines that changed since the round before (a line diff as difflib
    computes it, without context lines). Critiques are stored whole. A round reads back exactly as
    it was appended. Reading a round that depends on a damaged record raises CorruptChain instead
    of returning some other text; rounds before the damage still read back. An append is in the
    file when append returns, so a chain opened on the same path sees it.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, output: str, critique: str) -> int:
        """Store the next round and return its number (the first round is 0)."""
        records = self._records()
        number = len(records)
        record: dict = {"round": number}
        if number == 0:
            record["text"] = output
        else:
            record["ops"] = _diff(_rebuild(records)[-1], output)
        record["sha256"] = _digest(output, critique)
        record["critique"] = critique
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record) + "\n")
        return number

    def get(self, number: int) -> Revision:
        """Rebuild one round. Rounds outside 0 .. len(self) - 1 raise IndexError."""
        records = self._records()
        if not 0 <= number < len(records):
            raise IndexError(f"no round {number}; the chain has {len(records)}")
        output = _rebuild(records[: number + 1])[-1]
        return Revision(number, output, records[number]["critique"])

    def __len__(self) -> int:
        return len(self._records())

    def _records(self) -> list[dict | None]:
        """Every record in the file; None for a line that is not a JSON record (a torn or damaged write)."""
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        return [_parse(line) for line in text.split("\n") if line]


def _parse(line: str) -> dict | None:
    try:
        record = json.loads(line)
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def _rebuild(records: list[dict | None]) -> list[str]:
    """The outputs of these rounds, each checked against its digest."""
    outputs: list[str] = []
    for expected, record in enumerate(records):
        try:
            output = record["text"] if expected == 0 else _patch(outputs[-1], record["ops"])
            intact = record["round"] == expected and _digest(output, record["critique"]) == record["sha256"]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise CorruptChain(f"round {expected} is malformed") from exc
        if not intact:
            raise CorruptChain(f"round {expected} does not match what was appended")
        outputs.append(output)
    return outputs


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _join(lines: list[str]) -> str:
    return "".join(lines)


def _diff(old: str, new: str) -> list:
    """[i1, i2, new_lines] for every changed block: old lines i1..i2 become new_lines."""
    a, b = _lines(old), _lines(new)
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [[i1, i2, b[j1:j2]] for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def _patch(old: str, ops: list) -> str:
    lines = _lines(old)
    for i1, i2, new in reversed(ops):
        lines[i1:i2] = new
    return _join(lines)


def _digest(output: str, critique: str) -> str:
    return hashlib.sha256(json.dumps([output, critique]).encode("utf-8")).hexdigest()
