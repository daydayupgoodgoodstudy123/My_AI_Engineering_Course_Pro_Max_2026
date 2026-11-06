"""MFCC features for short mono clips, in pure Python.

frame -> Hann window -> |DFT| -> mel filterbank -> log -> DCT-II per frame,
then the frames are pooled over time into one fixed-length vector.
"""
from __future__ import annotations

import math


def hann(n: int) -> list[float]:
    return [0.5 * (1.0 - math.cos(2.0 * math.pi * i / (n - 1))) for i in range(n)]


def frame_signal(signal: list[float], frame_len: int, hop: int) -> list[list[float]]:
    """Cut a signal into frames of exactly frame_len samples, hop samples apart.

    A trailing partial frame is dropped, so a clip shorter than one frame has no frames.
    """
    if len(signal) < frame_len:
        return []
    n = 1 + (len(signal) - frame_len) // hop
    return [signal[i * hop : i * hop + frame_len] for i in range(n)]


def dft_mag(x: list[float]) -> list[float]:
    """Magnitudes of the first len(x) // 2 + 1 DFT bins."""
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


def stft_mag(signal: list[float], frame_len: int, hop: int) -> list[list[float]]:
    window = hann(frame_len)
    return [
        dft_mag([w * s for w, s in zip(window, frame)])
        for frame in frame_signal(signal, frame_len, hop)
    ]


def hz_to_mel(f: float) -> float:
    return 2595.0 * math.log10(1.0 + f / 700.0)


def mel_to_hz(m: float) -> float:
    return 700.0 * (10 ** (m / 2595.0) - 1.0)


def mel_filterbank(n_mels: int, n_fft: int, sr: int) -> list[list[float]]:
    """Triangular filters spaced evenly on the mel scale from 0 Hz to Nyquist."""
    top = hz_to_mel(sr / 2)
    mels = [top * i / (n_mels + 1) for i in range(n_mels + 2)]
    half = n_fft // 2 + 1
    bins = [min(half - 1, int(round(mel_to_hz(m) * n_fft / sr))) for m in mels]
    bank = [[0.0] * half for _ in range(n_mels)]
    for m in range(n_mels):
        left, center, right = bins[m], bins[m + 1], bins[m + 2]
        for k in range(left, center):
            bank[m][k] = (k - left) / max(1, center - left)
        for k in range(center, right):
            bank[m][k] = (right - k) / max(1, right - center)
    return bank


def apply_filterbank(spec: list[list[float]], bank: list[list[float]]) -> list[list[float]]:
    return [[sum(w * frame[k] for k, w in enumerate(f) if w) for f in bank] for frame in spec]


def log_transform(x: list[list[float]], eps: float = 1e-10) -> list[list[float]]:
    return [[math.log(max(v, eps)) for v in row] for row in x]


def dct_ii(x: list[float], n_coeffs: int) -> list[float]:
    n = len(x)
    return [
        sum(x[i] * math.cos(math.pi * k * (2 * i + 1) / (2 * n)) for i in range(n))
        for k in range(n_coeffs)
    ]


def featurize(
    signal: list[float],
    sr: int,
    n_mfcc: int = 13,
    n_mels: int = 26,
    frame_len: int = 128,
    hop: int = 64,
) -> list[list[float]]:
    """MFCC frames for one clip, one list of n_mfcc coefficients per frame."""
    mels = apply_filterbank(stft_mag(signal, frame_len, hop), mel_filterbank(n_mels, frame_len, sr))
    return [dct_ii(frame, n_mfcc) for frame in log_transform(mels)]


def summarize(frames: list[list[float]]) -> list[float]:
    """Pool MFCC frames over time: per-coefficient mean, then per-coefficient variance.

    The variance is the population variance (divide by the number of frames), as in the lesson.
    """
    if not frames:
        raise ValueError("cannot summarize a clip with no frames")
    t = len(frames)
    columns = list(zip(*frames))
    mean = [sum(col) / t for col in columns]
    var = [sum((v - m) ** 2 for v in col) / t for col, m in zip(columns, mean)]
    return mean + var
