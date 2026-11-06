"""Signal level of a frame, in dB relative to full scale."""
from __future__ import annotations

import math
from collections.abc import Sequence

FLOOR_DBFS = -200.0


def rms(frame: Sequence[float]) -> float:
    """Root mean square of a non-empty frame."""
    return math.sqrt(sum(x * x for x in frame) / len(frame))


def rms_dbfs(frame: Sequence[float]) -> float:
    """RMS level in dBFS, 20 * log10(rms).

    A full-scale square wave reads 0 dBFS and a full-scale sine -3.01 dBFS. Digital silence
    reads FLOOR_DBFS, and no frame reads lower.
    """
    level = rms(frame)
    if level <= 10 ** (FLOOR_DBFS / 20):
        return FLOOR_DBFS
    return 20.0 * math.log10(level)
