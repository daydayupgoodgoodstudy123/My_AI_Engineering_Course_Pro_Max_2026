"""Cepstral mean and variance normalization (CMVN), for whole utterances and for live streams."""
from __future__ import annotations

import math


def cmvn(frames: list[list[float]], floor: float = 1e-8) -> list[list[float]]:
    """Per-utterance CMVN: every feature dimension, over all frames, to mean 0 and unit variance.

    x' = (x - mean) / max(std, floor), with the population standard deviation (divide by
    the number of frames). The floor keeps a constant dimension, such as a band stuck at
    the log floor during silence, from dividing by zero.
    """
    if not frames:
        return []
    t = len(frames)
    columns = list(zip(*frames))
    means = [sum(col) / t for col in columns]
    scales = [
        max(math.sqrt(sum((v - m) ** 2 for v in col) / t), floor) for col, m in zip(columns, means)
    ]
    return [[(v - m) / s for v, m, s in zip(row, means, scales)] for row in frames]


class OnlineCMVN:
    """CMVN for a live stream of feature frames, using only frames that have already arrived.

    The first `warmup` frames are held back. When the last of them arrives they are
    released together, normalized with the statistics of exactly those frames, which is
    what cmvn() gives for that prefix. Every later frame is normalized on arrival with the
    statistics of all frames up to and including itself. flush() releases the frames still
    held back, normalized with the statistics of the frames seen so far.

    Each frame costs O(dim), and apart from the warm-up buffer memory does not grow with
    the length of the stream.
    """

    def __init__(self, dim: int, warmup: int = 100, floor: float = 1e-8) -> None:
        self.dim = dim
        self.warmup = warmup
        self.floor = floor
        self.count = 0
        self.mean = [0.0] * dim
        self.m2 = [0.0] * dim  # sum of squared deviations from the running mean (Welford)
        self.held: list[list[float]] = []

    def push(self, frames: list[list[float]]) -> list[list[float]]:
        """Add frames from the stream; return the normalized frames that are ready, oldest first."""
        out: list[list[float]] = []
        for frame in frames:
            self._update(frame)
            self.held.append(frame)
            if self.count >= self.warmup:
                out += [self._normalize(f) for f in self.held]
                self.held = []
        return out

    def flush(self) -> list[list[float]]:
        """End of stream: the frames still held back, normalized with the statistics so far."""
        out = [self._normalize(f) for f in self.held]
        self.held = []
        return out

    def _update(self, frame: list[float]) -> None:
        if len(frame) != self.dim:
            raise ValueError(f"expected {self.dim} values per frame, got {len(frame)}")
        self.count += 1
        for i, x in enumerate(frame):
            delta = x - self.mean[i]
            self.mean[i] += delta / self.count
            self.m2[i] += delta * (x - self.mean[i])

    def _normalize(self, frame: list[float]) -> list[float]:
        return [
            (x - m) / max(math.sqrt(m2 / self.count), self.floor)
            for x, m, m2 in zip(frame, self.mean, self.m2)
        ]
