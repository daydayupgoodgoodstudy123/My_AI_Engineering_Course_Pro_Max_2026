"""Memory blocks: labeled, size-capped sections of core memory that the model edits with tools."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """One block of core memory (Human, Persona, Task, ...), always in the prompt.

    The value is a list of lines joined by "\\n". limit caps its length in characters,
    newlines included. Every write bumps version and pushes the previous value onto history.
    A write that would take the value past limit is refused: it returns an observation that
    starts with "error:" and leaves value, version and history as they were.
    """

    label: str
    value: str = ""
    limit: int = 300
    description: str = ""
    version: int = 0
    history: list[str] = field(default_factory=list)

    def append(self, text: str) -> str:
        """block_append: add text as a new last line."""
        return self._commit(f"{self.value}\n{text}" if self.value else text, "append")

    def replace(self, old: str, new: str) -> str:
        """block_replace: replace every occurrence of old, which must be a non-empty part of the value."""
        if old not in self.value:
            return f"error: {old!r} not in {self.label}"
        return self._commit(self.value.replace(old, new), "replace")

    def rewrite(self, new: str) -> str:
        """Replace the whole value. This is how the sleep-time agent writes."""
        return self._commit(new, "rewrite")

    def near_limit(self, threshold: float = 0.8) -> bool:
        return len(self.value) >= int(self.limit * threshold)

    def _commit(self, value: str, op: str) -> str:
        self.history.append(self.value)
        self.value = value
        self.version += 1
        return f"{self.label} v{self.version} {op} ({len(self.value)}/{self.limit})"


class BlockStore:
    """The core tier: every block, rendered into the prompt in label order."""

    def __init__(self) -> None:
        self._blocks: dict[str, Block] = {}

    def create(self, label: str, description: str, limit: int = 300) -> Block:
        if label in self._blocks:
            raise ValueError(f"block {label!r} already exists")
        block = Block(label=label, description=description, limit=limit)
        self._blocks[label] = block
        return block

    def get(self, label: str) -> Block:
        """The block with this label. Unknown labels raise KeyError."""
        return self._blocks[label]

    def labels(self) -> list[str]:
        return sorted(self._blocks)

    def render(self) -> str:
        lines: list[str] = []
        for label in self.labels():
            block = self._blocks[label]
            lines.append(f"[{label} v{block.version} {len(block.value)}/{block.limit}] {block.description}")
            lines.extend(f"  {line}" for line in block.value.split("\n"))
        return "\n".join(lines)


def summarize(text: str, target_len: int) -> str:
    """Condense a block value to at most target_len characters for a sleep-time rewrite.

    Keeps as many of the newest lines as fit, whole and in their original order (blocks
    grow at the bottom, so the newest facts are last). Returns "" when not even the newest
    line fits.
    """
    kept: list[str] = []
    used = 0
    for line in reversed(text.split("\n")):
        if used + len(line) > target_len:
            break
        kept.append(line)
        used += len(line)
    return "\n".join(reversed(kept))
