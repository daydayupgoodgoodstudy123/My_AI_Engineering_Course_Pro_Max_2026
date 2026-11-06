"""The refine history on disk: round 0 in full, then one line diff per round."""
from __future__ import annotations

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
        raise NotImplementedError

    def get(self, number: int) -> Revision:
        """Rebuild one round. Rounds outside 0 .. len(self) - 1 raise IndexError."""
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError
