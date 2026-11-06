"""Delta features: frame-to-frame dynamics stacked onto static log-mel or MFCC frames."""
from __future__ import annotations

from collections.abc import Sequence


def deltas(frames: list[list[float]], width: int = 2) -> list[list[float]]:
    """Regression deltas of every feature dimension over +-width frames:

        d[t] = sum(n * (c[t + n] - c[t - n]) for n in 1..width) / (2 * sum(n * n for n in 1..width))

    Frames before the first and after the last are copies of the first and last frame, so
    the output has as many frames as the input.
    """
    if width < 1:
        raise ValueError(f"width must be at least 1, got {width}")
    last = len(frames) - 1
    denom = 2 * sum(n * n for n in range(1, width + 1))
    out = []
    for t in range(len(frames)):
        acc = [0.0] * len(frames[t])
        for n in range(1, width + 1):
            ahead, behind = frames[min(t + n, last)], frames[max(t - n, 0)]
            for i, (a, b) in enumerate(zip(ahead, behind)):
                acc[i] += n * (a - b)
        out.append([v / denom for v in acc])
    return out


def add_deltas(frames: list[list[float]], windows: Sequence[int] = (2, 2)) -> list[list[float]]:
    """Stack each frame with its deltas: static, then order 1, order 2, ...

    windows[i] is the regression width of order i + 1, and order i + 1 is the delta of
    order i, so order 2 (delta-delta) is the delta of the deltas. No windows: static only.
    """
    blocks = [frames]
    for width in windows:
        blocks.append(deltas(blocks[-1], width))
    return [[v for block in blocks for v in block[t]] for t in range(len(frames))]
