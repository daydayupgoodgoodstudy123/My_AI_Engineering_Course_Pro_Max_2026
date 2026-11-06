"""Cepstral mean and variance normalization (CMVN), for whole utterances and for live streams."""
from __future__ import annotations


def cmvn(frames: list[list[float]], floor: float = 1e-8) -> list[list[float]]:
    """Per-utterance CMVN: every feature dimension, over all frames, to mean 0 and unit variance.

    x' = (x - mean) / max(std, floor), with the population standard deviation (divide by
    the number of frames). The floor keeps a constant dimension, such as a band stuck at
    the log floor during silence, from dividing by zero.
    """
    raise NotImplementedError


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

    def push(self, frames: list[list[float]]) -> list[list[float]]:
        """Add frames from the stream; return the normalized frames that are ready, oldest first."""
        raise NotImplementedError

    def flush(self) -> list[list[float]]:
        """End of stream: the frames still held back, normalized with the statistics so far."""
        raise NotImplementedError
