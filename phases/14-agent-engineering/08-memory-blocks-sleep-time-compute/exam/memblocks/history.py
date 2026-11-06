"""Block version history on disk, so an operator can see what a block said at any version."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .blocks import Block

OPS = ("append", "replace", "rewrite")


@dataclass(frozen=True)
class Version:
    version: int
    op: str  # one of OPS
    value: str  # the whole value after the write


class BlockLog:
    """Append-only version logs, one file per block: <root>/<label>.log.

    Each version is one line: a JSON object with version, op and value, ending with a newline.
    Labels are lowercase names (letters, digits, underscores, starting with a letter), so they
    are safe file names; any other label is a ValueError.

    A crash can leave a torn last line with no newline. Reading the log drops it, and the next
    version is written where the torn line began.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, label: str, version: int, op: str, value: str) -> None:
        """Log one version of a block, written to disk before this returns.

        A block's versions are consecutive from 1, across reopens too, so any other version
        number is a ValueError, and so is an op outside OPS.
        """
        raise NotImplementedError

    def versions(self, label: str) -> list[Version]:
        """Every logged version of a block, oldest first. A block with no log has none."""
        raise NotImplementedError

    def value_at(self, label: str, version: int) -> str:
        """The block's value at that version. Version 0 is the new, empty block.

        Versions that were never logged raise KeyError.
        """
        raise NotImplementedError

    def restore(self, label: str, limit: int, description: str = "") -> Block:
        """The block as of its last logged version: its value, version and history."""
        raise NotImplementedError
