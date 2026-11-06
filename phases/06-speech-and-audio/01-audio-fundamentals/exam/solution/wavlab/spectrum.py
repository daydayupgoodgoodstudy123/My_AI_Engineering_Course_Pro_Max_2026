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
    n = len(samples)
    if n < 4:
        raise ValueError("need at least 4 samples")
    mean = sum(samples) / n
    mags = dft_magnitudes([(x - mean) * w for x, w in zip(samples, hann(n))])
    k = max(range(1, n // 2), key=mags.__getitem__)
    if mags[k] == 0.0:
        raise ValueError("no tone: the clip is silent once the mean is removed")
    a, b, c = (math.log(max(m, 1e-300)) for m in mags[k - 1 : k + 2])
    curve = a - 2 * b + c
    offset = 0.5 * (a - c) / curve if curve else 0.0
    return (k + offset) * sample_rate / n


def alias_frequency(freq: float, sample_rate: int) -> float:
    """Where a tone of freq Hz shows up once sampled at sample_rate: a frequency in [0, sample_rate / 2]."""
    folded = abs(freq) % sample_rate
    return sample_rate - folded if folded > sample_rate / 2 else folded
