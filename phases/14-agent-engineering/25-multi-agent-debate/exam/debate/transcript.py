"""Debate transcripts in a compact binary file.

Layout (every count, round and index is an unsigned LEB128 varint: 7 bits per byte, low
group first, the high bit set on every byte except the last):

    transcript := MAGIC  varint(len(roster))  text*  varint(len(turns))  turn*
    turn       := varint(round)  varint(debater)  text(answer)  f64(confidence)
                  varint(len(read))  varint(peer)*
    text       := varint(number of UTF-8 bytes)  UTF-8 bytes
    f64        := IEEE 754 double, big-endian

debater and peer are positions in the roster. Nothing may follow the last turn.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAGIC = b"DBT\x01"


@dataclass(frozen=True)
class Turn:
    round: int
    debater: int  # roster position of the debater who spoke
    answer: str
    confidence: float  # in [0, 1]
    read: tuple[int, ...]  # roster positions of the peers it read, in reading order


class Transcript:
    """Every turn of one debate, in the order the turns were added."""

    def __init__(self, roster: list[str]) -> None:
        if len(set(roster)) != len(roster):
            raise ValueError("debater names must be unique")
        self.roster = list(roster)
        self.turns: list[Turn] = []

    def add(self, turn: Turn) -> None:
        """Append a turn. A turn that could not have happened raises ValueError: a round below
        0, a debater or peer outside the roster, a debater reading itself or the same peer
        twice, or a confidence outside [0, 1]."""
        raise NotImplementedError

    def to_bytes(self) -> bytes:
        """The transcript in the layout described at the top of this module."""
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes) -> Transcript:
        """Rebuild a transcript. Damaged data (another magic, a cut-off file, trailing bytes,
        or a turn that add() would refuse) raises ValueError."""
        raise NotImplementedError

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.to_bytes())

    @classmethod
    def load(cls, path: str | Path) -> Transcript:
        return cls.from_bytes(Path(path).read_bytes())

