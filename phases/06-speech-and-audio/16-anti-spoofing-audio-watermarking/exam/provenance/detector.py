"""A toy spectral spoof detector, in pure Python.

Synthetic speech often carries unusual energy high in the spectrum. The detector averages the
power spectrum of a clip's frames and scores the share of the clip's energy that sits at or
above a cutoff frequency, in decibels. Production systems use AASIST or RawNet2 instead.
"""
from __future__ import annotations

import math
from functools import lru_cache

FLOOR_DB = -100.0


def hann(n: int) -> list[float]:
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]


@lru_cache(maxsize=None)
def _twiddles(n: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """cos and sin of 2 pi m / n, for m = 0 .. n - 1."""
    return (
        tuple(math.cos(2.0 * math.pi * m / n) for m in range(n)),
        tuple(math.sin(2.0 * math.pi * m / n) for m in range(n)),
    )


def frame_starts(n_samples: int, n_fft: int) -> range:
    """Start of every full frame of n_fft samples.

    Frames do not overlap. A trailing partial frame is dropped.
    """
    return range(0, n_samples - n_fft, n_fft)


def power_spectrum(frame: list[float]) -> list[float]:
    """Power |X[k]|^2 of the Hann-windowed frame, for the one-sided bins k = 0 .. len(frame) // 2."""
    n = len(frame)
    cos_t, sin_t = _twiddles(n)
    x = [w * s for w, s in zip(hann(n), frame)]
    out = []
    for k in range(n // 2 + 1):
        re = im = 0.0
        m = 0  # k * j mod n
        for v in x:
            re += v * cos_t[m]
            im -= v * sin_t[m]
            m += k
            if m >= n:
                m -= n
        out.append(math.sqrt(re * re + im * im))
    return out


def average_spectrum(audio: list[float], n_fft: int = 256) -> list[float]:
    """Mean power of each one-sided bin over the clip's full frames.

    A clip shorter than one frame raises ValueError.
    """
    if len(audio) < n_fft:
        raise ValueError(f"{len(audio)} samples is shorter than one {n_fft}-sample frame")
    starts = frame_starts(len(audio), n_fft)
    return [
        sum(power_spectrum(audio[s : s + n_fft])[k] for s in starts) / len(starts)
        for k in range(n_fft // 2 + 1)
    ]


def bin_hz(k: int, sr: int, n_fft: int) -> float:
    """Centre frequency of bin k of an n_fft-point DFT."""
    return k * sr / n_fft


def high_band(spec: list[float], sr: int, cutoff_hz: float) -> list[float]:
    """The bins of a one-sided spectrum whose centre frequency is at or above cutoff_hz."""
    n_fft = len(spec)
    return [p for k, p in enumerate(spec) if bin_hz(k, sr, n_fft) >= cutoff_hz]


def toy_detector_score(audio: list[float], sr: int, n_fft: int = 256, cutoff_hz: float = 4000.0) -> float:
    """Spoof score in dB: 10 log10 of the share of the clip's energy at or above cutoff_hz.

    Higher looks more synthetic, and 0 dB means all of the energy is up there. The score is
    clipped at FLOOR_DB, which is also the score of silence.
    """
    spec = average_spectrum(audio, n_fft)
    share = (sum(high_band(spec, sr, cutoff_hz)) + 1e-12) / (sum(spec) + 1e-12)
    return max(FLOOR_DB, 10.0 * math.log10(share))
