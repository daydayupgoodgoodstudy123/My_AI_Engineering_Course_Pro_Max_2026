"""Tier 1 of the VAD cascade: an energy gate over fixed-length frames.

Levels are RMS values in dBFS, 20 * log10(RMS), with full scale (1.0) at 0 dBFS. The gate
compares each frame with the threshold without taking a logarithm, then a short hangover
keeps the dips between syllables inside the speech.
"""
from __future__ import annotations

import math

FLOOR_DBFS = -120.0


def rms(samples: list[float]) -> float:
    """Root mean square: the square root of the mean of the squared samples."""
    return math.sqrt(sum(x * x for x in samples) / len(samples))


def dbfs(level: float) -> float:
    """An RMS level in dB relative to full scale, floored at FLOOR_DBFS (digital silence is 0.0)."""
    if level == 0.0:
        return FLOOR_DBFS
    return max(FLOOR_DBFS, 20.0 * math.log10(level))


def frame_levels(signal: list[float], frame_len: int) -> list[float]:
    """The dBFS level of every complete frame. A trailing partial frame is ignored."""
    return [
        dbfs(rms(signal[start : start + frame_len]))
        for start in range(0, len(signal) - frame_len + 1, frame_len)
    ]


def apply_hangover(loud: list[bool], frames: int) -> list[bool]:
    """Frame i is speech when it is loud, or when the last loud frame before it is at most frames back."""
    out: list[bool] = []
    last = None
    for i, is_loud in enumerate(loud):
        if is_loud:
            last = i
        out.append(last is not None and i - last <= frames)
    return out


def energy_gate(
    signal: list[float],
    sample_rate: int,
    threshold_dbfs: float = -40.0,
    frame_ms: int = 20,
    hangover_ms: int = 100,
) -> list[bool]:
    """One speech flag per complete frame of frame_ms.

    A frame is loud when its RMS level is above threshold_dbfs. A loud frame, and every frame
    up to hangover_ms after it, is speech.
    """
    frame_len = sample_rate * frame_ms // 1000
    limit = 10.0 ** (threshold_dbfs / 20.0)
    loud = []
    for start in range(0, len(signal) - frame_len + 1, frame_len):
        frame = signal[start : start + frame_len]
        power = sum(x * x for x in frame) / frame_len
        loud.append(power > limit * limit)
    return apply_hangover(loud, hangover_ms // frame_ms)
