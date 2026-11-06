"""Block version history on disk, so an operator can see what a block said at any version."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .blocks import Block

OPS = ("append", "replace", "rewrite")
LABEL = re.compile(r"[a-z][a-z0-9_]*")


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
        self._loaded: dict[str, list[Version]] = {}

    def record(self, label: str, version: int, op: str, value: str) -> None:
        """Log one version of a block, written to disk before this returns.

        A block's versions are consecutive from 1, across reopens too, so any other version
        number is a ValueError, and so is an op outside OPS.
        """
        versions = self._load(label)
        if op not in OPS:
            raise ValueError(f"unknown op {op!r}, expected one of {OPS}")
        if version != len(versions) + 1:
            raise ValueError(f"{label} is at v{len(versions)}, so the next version is {len(versions) + 1}")
        line = json.dumps({"version": version, "op": op, "value": value}) + "\n"
        with self._path(label).open("a", encoding="utf-8") as log:
            log.write(line)
            log.flush()
            os.fsync(log.fileno())
        versions.append(Version(version, op, value))

    def versions(self, label: str) -> list[Version]:
        """Every logged version of a block, oldest first. A block with no log has none."""
        return list(self._load(label))

    def value_at(self, label: str, version: int) -> str:
        """The block's value at that version. Version 0 is the new, empty block.

        Versions that were never logged raise KeyError.
        """
        versions = self._load(label)
        if version == 0:
            return ""
        if not 1 <= version <= len(versions):
            raise KeyError(version)
        return versions[version - 1].value

    def restore(self, label: str, limit: int, description: str = "") -> Block:
        """The block as of its last logged version: its value, version and history."""
        values = [""] + [v.value for v in self._load(label)]
        return Block(label, values[-1], limit, description, len(values) - 1, values[:-1])

    def _path(self, label: str) -> Path:
        if not LABEL.fullmatch(label):
            raise ValueError(f"bad block label {label!r}")
        return self.root / f"{label}.log"

    def _load(self, label: str) -> list[Version]:
        path = self._path(label)
        if label not in self._loaded:
            versions: list[Version] = []
            if path.exists():
                data = path.read_bytes()
                end = data.rfind(b"\n") + 1
                if end < len(data):  # a torn last line: cut it off so the next write starts clean
                    with path.open("r+b") as log:
                        log.truncate(end)
                for line in data[:end].split(b"\n")[:-1]:
                    row = json.loads(line)
                    versions.append(Version(row["version"], row["op"], row["value"]))
            self._loaded[label] = versions
        return self._loaded[label]
