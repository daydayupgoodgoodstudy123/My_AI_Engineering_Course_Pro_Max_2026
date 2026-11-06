"""Blind spread-spectrum watermark for converted speech.

Sample i of a clip carries payload bit i % n_bits. The mark added to it is
strength * (+1 for a 1 bit, -1 for a 0 bit) * chip_i, where chip_0, chip_1, ... is a
pseudo-random +1/-1 sequence that depends only on the secret key. The detector never sees
the original audio: it correlates the received samples with the same chips, so the speech
averages out and the mark adds up.
"""
from __future__ import annotations

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass



def int_to_bits(value: int, n_bits: int) -> list[int]:
    """value as n_bits bits, most significant first."""
    if not 0 <= value < 1 << n_bits:
        raise ValueError(f"{value} does not fit in {n_bits} bits")
    return [(value >> (n_bits - 1 - i)) & 1 for i in range(n_bits)]


def bits_to_int(bits: list[int]) -> int:
    """The inverse of int_to_bits."""
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


def bit_accuracy(expected: list[int], observed: list[int | None]) -> float:
    """Fraction of the payload bits the detector got right.

    observed has one entry per payload bit. None means the detector had no evidence for
    that bit, and it counts as wrong. Lists of different lengths raise ValueError.
    """
    if len(expected) != len(observed):
        raise ValueError(f"{len(observed)} observed bits for a {len(expected)}-bit payload")
    if not expected:
        raise ValueError("the payload is empty")
    right = sum(o is not None and o == e for e, o in zip(expected, observed))
    return right / len(expected)


@dataclass(frozen=True)
class Detection:
    """What the detector read from a clip.

    bits[b] is the decoded payload bit, or None when no sample carried evidence for it.
    scores[b] is the z-score of bit b (see Evidence.scores).
    """

    bits: list[int | None]
    scores: list[float]
    threshold: float

    @property
    def found(self) -> bool:
        """True when every bit's |score| reaches the threshold."""
        return bool(self.scores) and all(abs(z) >= self.threshold for z in self.scores)


class Evidence:
    """Correlation of received audio with a key's chips, accumulated bit by bit.

    Feed samples in stream order with add(); how they are split across calls does not matter.
    """

    def __init__(self, watermarker: Watermarker) -> None:
        self.n_bits = watermarker.n_bits
        self.samples = 0
        self._chips = watermarker.chips()
        self._corr = [0.0] * self.n_bits
        self._energy = [0.0] * self.n_bits

    def add(self, samples: list[float]) -> None:
        corr, energy, chips = self._corr, self._energy, self._chips
        b = self.samples % self.n_bits
        for x in samples:
            corr[b] += x * next(chips)
            energy[b] += x * x
            b += 1
            if b == self.n_bits:
                b = 0
        self.samples += len(samples)

    def scores(self) -> list[float]:
        """Bit b's correlation divided by the root energy of the samples that carried it.

        The score does not change with playback volume, and without a mark it is roughly
        standard normal. A bit with no energy scores 0.0.
        """
        return [c / math.sqrt(e) if e > 0.0 else 0.0 for c, e in zip(self._corr, self._energy)]

    def bits(self) -> list[int | None]:
        """1 for a positive correlation, 0 otherwise, None for a bit with no energy."""
        return [None if e == 0.0 else int(c > 0.0) for c, e in zip(self._corr, self._energy)]


class Watermarker:
    """Stamps and reads an n_bits payload with a secret key."""

    def __init__(self, key: int, n_bits: int = 16, strength: float = 0.005, threshold: float = 4.0) -> None:
        self.key = key
        self.n_bits = n_bits
        self.strength = strength
        self.threshold = threshold

    def chips(self) -> Iterator[int]:
        """The key's chip sequence from its start: the same +1/-1 values on every call, in every process."""
        rng = random.Random(self.key)
        while True:
            yield 1 if rng.random() < 0.5 else -1

    def embed(self, audio: list[float], bits: list[int]) -> list[float]:
        """A marked copy of audio carrying the payload bits. audio itself is not changed."""
        if len(bits) != self.n_bits:
            raise ValueError(f"the payload must have {self.n_bits} bits, got {len(bits)}")
        signs = [1.0 if bit else -1.0 for bit in bits]
        chips = self.chips()
        n = self.n_bits
        return [x + self.strength * signs[i % n] * next(chips) for i, x in enumerate(audio)]

    def evidence(self) -> Evidence:
        """A fresh accumulator for one clip or one live stream."""
        return Evidence(self)

    def verdict(self, evidence: Evidence) -> Detection:
        return Detection(evidence.bits(), evidence.scores(), self.threshold)

    def detect(self, audio: list[float]) -> Detection:
        """Read the payload from the received audio alone (blind detection)."""
        evidence = self.evidence()
        evidence.add(audio)
        return self.verdict(evidence)
