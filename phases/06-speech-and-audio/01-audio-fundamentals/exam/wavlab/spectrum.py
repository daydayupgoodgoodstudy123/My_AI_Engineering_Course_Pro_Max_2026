"""Tones in short clips: the lesson's plain DFT, a peak estimate between bins, and aliasing."""
from __future__ import annotations

import math


def hann(n: int) -> list[float]:
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]


def dft_magnitudes(x: list[float]) -> list[float]:
    """|X[k]| for k = 0 .. len(x) // 2, the non-negative frequencies (real input mirrors the rest).

    Bin k is k * sample_rate / len(x) Hz. This is the lesson's O(N^2) DFT.
    """
    n = len(x)
    out = []
    for k in range(n // 2 + 1):
        re = im = 0.0
        for j, v in enumerate(x):
            angle = -2.0 * math.pi * k * j / n
            re += v * math.cos(angle)
            im += v * math.sin(angle)
        out.append(math.hypot(re, im))
    return out


def dominant_frequency(samples: list[float], sample_rate: int) -> float:
    """Frequency in Hz of the strongest tone in a clip, estimated between DFT bins.

    Subtract the mean (a DC offset is not a tone), apply a Hann window, and find the bin k with
    the largest magnitude among bins 1 .. N/2 - 1. Then fit a parabola through the log
    magnitudes of bins k - 1, k and k + 1; its vertex is the estimate, in fractional bins.
    Clips shorter than 4 samples, or silent once the mean is removed, raise ValueError.
    """
    raise NotImplementedError


def alias_frequency(freq: float, sample_rate: int) -> float:
    """Where a tone of freq Hz shows up once sampled at sample_rate: a frequency in [0, sample_rate / 2]."""
    raise NotImplementedError
