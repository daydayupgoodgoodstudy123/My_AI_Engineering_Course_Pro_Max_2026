"""Log-mel features for short mono clips, in pure Python.

frame -> Hann window -> power spectrum -> mel filterbank -> log, dB or Whisper scaling, one row per frame.
"""
from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from functools import lru_cache


def hann(n: int) -> list[float]:
    """Symmetric Hann window of n samples; both ends are 0."""
    return [0.5 * (1.0 - math.cos(2.0 * math.pi * i / (n - 1))) for i in range(n)]


def frame_signal(signal: list[float], frame_len: int, hop: int) -> list[list[float]]:
    """Frames of exactly frame_len samples, hop samples apart. A trailing partial frame is dropped."""
    if len(signal) < frame_len:
        return []
    n = 1 + (len(signal) - frame_len) // hop
    return [signal[i * hop : i * hop + frame_len] for i in range(n)]


@lru_cache(maxsize=8)
def _dft_rows(n: int) -> tuple[list[list[float]], list[list[float]]]:
    """cos and sin of 2*pi*k*j/n for the first n // 2 + 1 bins k, one row per bin."""
    cos = [math.cos(2.0 * math.pi * i / n) for i in range(n)]
    sin = [math.sin(2.0 * math.pi * i / n) for i in range(n)]
    bins = range(n // 2 + 1)
    return (
        [[cos[k * j % n] for j in range(n)] for k in bins],
        [[sin[k * j % n] for j in range(n)] for k in bins],
    )


def power_spectrum(frame: list[float]) -> list[float]:
    """Power |X[k]|^2 of the first len(frame) // 2 + 1 DFT bins of one frame."""
    cos_rows, sin_rows = _dft_rows(len(frame))
    out = []
    for c, s in zip(cos_rows, sin_rows):
        re = sum(map(operator.mul, frame, c))
        im = sum(map(operator.mul, frame, s))
        out.append(re * re + im * im)
    return out


def hz_to_mel(f: float) -> float:
    """HTK mel scale: m = 2595 * log10(1 + f / 700), so 1000 Hz is about 1000 mel."""
    return 2595.0 * math.log(1.0 + f / 700.0)


def mel_to_hz(m: float) -> float:
    """Inverse of hz_to_mel."""
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


@dataclass(frozen=True)
class MelFilter:
    """One triangular mel filter, stored as its run of nonzero weights."""

    start: int  # first FFT bin the filter covers
    weights: tuple[float, ...]  # weights for bins start, start + 1, ...

    def dense(self, n_bins: int) -> list[float]:
        """The filter as a full row of n_bins weights, zero outside its span."""
        row = [0.0] * n_bins
        row[self.start : self.start + len(self.weights)] = self.weights
        return row


def mel_filterbank(
    n_mels: int, n_fft: int, sr: int = 16000, fmin: float = 0.0, fmax: float | None = None
) -> list[MelFilter]:
    """Triangular filters for the n_fft-point spectrum of audio sampled at sr Hz.

    Filter edges are evenly spaced on the mel scale from fmin to fmax; fmax defaults to
    Nyquist. Filter m rises from edge m to a peak of 1.0 at edge m + 1 and falls back to 0
    at edge m + 2; every edge is rounded to the nearest FFT bin. A filter that covers no FFT
    bin is an error.
    """
    fmax = sr / 2 if fmax is None else fmax
    lo, hi = hz_to_mel(fmin), hz_to_mel(fmax)
    top = n_fft // 2
    edges = [
        min(top, round(mel_to_hz(lo + (hi - lo) * i / (n_mels + 1)) * n_fft / sr))
        for i in range(n_mels + 2)
    ]
    filters = []
    for m in range(n_mels):
        left, center, right = edges[m], edges[m + 1], edges[m + 2]
        weights = tuple(
            (k - left) / (center - left) if k <= center else (right - k) / (right - center)
            for k in range(left + 1, right)
        )
        if not weights:
            raise ValueError(f"mel filter {m} of {n_mels} covers no FFT bins (n_fft={n_fft}, sr={sr})")
        filters.append(MelFilter(left + 1, weights))
    return filters


def apply_filterbank(spec: list[list[float]], filters: list[MelFilter]) -> list[list[float]]:
    """Mel energies, one row per frame: each filter's weighted sum of the power spectrum."""
    n_bins = len(spec[0]) if spec else 0
    matrix = [f.dense(n_bins) for f in filters]
    return [[sum(row[k] * frame[k] for k in range(n_bins)) for row in matrix] for frame in spec]


def log_mel(mel: list[list[float]], floor: float = 1e-10) -> list[list[float]]:
    """Natural log of mel energies.

    Energies below floor are raised to floor before the log, so digital silence gives
    log(floor); every other energy keeps its exact log.
    """
    return [[math.log(max(v, floor)) for v in row] for row in mel]


def power_to_db(power: list[list[float]], ref: float = 1.0, amin: float = 1e-10) -> list[list[float]]:
    """Decibels of power values: 10 * log10(max(p, amin) / ref)."""
    return [[10.0 * math.log10(max(p, amin) / ref) for p in row] for row in power]


def whisper_log_mel(mel: list[list[float]], floor: float = 1e-10) -> list[list[float]]:
    """Whisper's scaling of mel power, as in its log_mel_spectrogram.

    Every value becomes log10(max(v, floor)). Values more than 8 (80 dB) below the loudest
    value in the whole clip are raised to that level, and the result is mapped by (x + 4) / 4.
    """
    out = []
    for row in mel:
        logs = [math.log10(max(v, floor)) for v in row]
        top = max(logs)
        out.append([(max(x, top - 8.0) + 4.0) / 4.0 for x in logs])
    return out


def log_mel_spectrogram(
    signal: list[float],
    sr: int,
    n_fft: int = 400,
    hop: int = 160,
    n_mels: int = 80,
    fmin: float = 0.0,
    fmax: float | None = None,
    kind: str = "log",
    floor: float = 1e-10,
) -> list[list[float]]:
    """Log-mel features of a clip sampled at sr Hz, one row of n_mels values per frame of n_fft samples.

    kind="log" is the natural log of mel power, kind="db" is mel power in decibels, and
    kind="whisper" is Whisper's scaled log10 (see whisper_log_mel).
    """
    window = hann(n_fft)
    spec = [
        power_spectrum([w * s for w, s in zip(window, frame)])
        for frame in frame_signal(signal, n_fft, hop)
    ]
    mel = apply_filterbank(spec, mel_filterbank(n_mels, n_fft, fmin=fmin, fmax=fmax))
    if kind == "log":
        return log_mel(mel, floor)
    if kind == "db":
        return power_to_db(mel, amin=floor)
    if kind == "whisper":
        return whisper_log_mel(mel, floor)
    raise ValueError(f"kind must be 'log', 'db' or 'whisper', got {kind!r}")
