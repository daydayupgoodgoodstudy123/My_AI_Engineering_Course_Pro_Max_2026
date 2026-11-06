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

import struct
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
        n = len(self.roster)
        if turn.round < 0:
            raise ValueError(f"round must be >= 0, got {turn.round}")
        if not 0 <= turn.debater < n:
            raise ValueError(f"debater {turn.debater} is not in the roster")
        if not 0.0 <= turn.confidence <= 1.0:  # also rejects NaN
            raise ValueError(f"confidence must be in [0, 1], got {turn.confidence!r}")
        for peer in turn.read:
            if not 0 <= peer < n:
                raise ValueError(f"peer {peer} is not in the roster")
            if peer == turn.debater:
                raise ValueError(f"debater {turn.debater} cannot read itself")
        if len(set(turn.read)) != len(turn.read):
            raise ValueError(f"debater {turn.debater} reads a peer twice")
        self.turns.append(turn)

    def to_bytes(self) -> bytes:
        out = bytearray(MAGIC)
        out += _varint(len(self.roster))
        for name in self.roster:
            out += _text(name)
        out += _varint(len(self.turns))
        for t in self.turns:
            out += _varint(t.round) + _varint(t.debater) + _text(t.answer)
            out += struct.pack(">d", t.confidence)
            out += _varint(len(t.read))
            for peer in t.read:
                out += _varint(peer)
        return bytes(out)

    @classmethod
    def from_bytes(cls, data: bytes) -> Transcript:
        """Rebuild a transcript. Damaged data (another magic, a cut-off file, trailing bytes,
        or a turn that add() would refuse) raises ValueError."""
        reader = _Reader(data)
        if reader.take(len(MAGIC)) != MAGIC:
            raise ValueError("not a debate transcript")
        transcript = cls([reader.text() for _ in range(reader.varint())])
        for _ in range(reader.varint()):
            round_, debater, answer = reader.varint(), reader.varint(), reader.text()
            (confidence,) = struct.unpack(">d", reader.take(8))
            read = tuple(reader.varint() for _ in range(reader.varint()))
            transcript.add(Turn(round_, debater, answer, confidence, read))
        if reader.pos != len(data):
            raise ValueError(f"{len(data) - reader.pos} unexpected bytes after the last turn")
        return transcript

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.to_bytes())

    @classmethod
    def load(cls, path: str | Path) -> Transcript:
        return cls.from_bytes(Path(path).read_bytes())


def _varint(n: int) -> bytes:
    if n < 0:
        raise ValueError(f"varints are unsigned, got {n}")
    out = bytearray()
    while True:
        low, n = n & 0x7F, n >> 7
        if n:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def _text(s: str) -> bytes:
    raw = s.encode("utf-8")
    return _varint(len(raw)) + raw


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError("transcript is cut off")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def varint(self) -> int:
        value = shift = 0
        while True:
            byte = self.take(1)[0]
            value |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return value

    def text(self) -> str:
        return self.take(self.varint()).decode("utf-8")

