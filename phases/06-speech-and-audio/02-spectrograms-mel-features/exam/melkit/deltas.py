"""Delta features: frame-to-frame dynamics stacked onto static log-mel or MFCC frames."""
from __future__ import annotations

from collections.abc import Sequence


def deltas(frames: list[list[float]], width: int = 2) -> list[list[float]]:
    """Regression deltas of every feature dimension over +-width frames:

        d[t] = sum(n * (c[t + n] - c[t - n]) for n in 1..width) / (2 * sum(n * n for n in 1..width))

    Frames before the first and after the last are copies of the first and last frame, so
    the output has as many frames as the input.
    """
    raise NotImplementedError


def add_deltas(frames: list[list[float]], windows: Sequence[int] = (2, 2)) -> list[list[float]]:
    """Stack each frame with its deltas: static, then order 1, order 2, ...

    windows[i] is the regression width of order i + 1, and order i + 1 is the delta of
    order i, so order 2 (delta-delta) is the delta of the deltas. No windows: static only.
    """
    raise NotImplementedError
