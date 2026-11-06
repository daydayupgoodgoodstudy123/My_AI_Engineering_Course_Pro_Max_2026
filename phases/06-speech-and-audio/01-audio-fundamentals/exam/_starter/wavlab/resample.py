"""Downsampling with an anti-aliasing filter: low-pass first, then keep every factor-th sample."""
from __future__ import annotations

import math
from collections.abc import AsyncIterator


def lowpass_taps(factor: int, n_taps: int = 31) -> list[float]:
    """Hamming-windowed sinc low-pass for decimating by factor.

    The cutoff is 90% of the new Nyquist frequency, and the taps sum to 1 (unity gain at DC).
    """
    cutoff = 0.45 / factor  # cycles per input sample
    middle = (n_taps - 1) / 2
    taps = []
    for k in range(n_taps):
        t = k - middle
        ideal = 2 * cutoff if t == 0 else math.sin(2 * math.pi * cutoff * t) / (math.pi * t)
        taps.append(ideal * (0.54 - 0.46 * math.cos(2 * math.pi * k / (n_taps - 1))))
    total = sum(taps)
    return [h / total for h in taps]


def decimate(samples: list[float], factor: int) -> list[float]:
    """Low-pass filter, then keep samples 0, factor, 2 * factor, ... of the filtered signal.

    Output m is the sum of taps[k] * samples[m * factor - k] over k = 0, 1, ..., with samples
    before the start taken as 0. The filter is causal: output m needs no input after m * factor.
    """
    if factor < 1:
        raise ValueError("factor must be a positive integer")
    taps = lowpass_taps(factor)
    out = []
    for n in range(0, len(samples), factor):
        acc = 0.0
        for k, h in enumerate(taps[: n + 1]):
            acc += h * samples[n - k]
        out.append(acc)
    return out


async def stream_downsample(chunks: AsyncIterator[bytes], factor: int) -> AsyncIterator[bytes]:
    """Downsample a live mono 16-bit PCM stream by factor as it arrives.

    chunks are reads from a socket: little-endian int16 samples cut at arbitrary byte
    boundaries, so a chunk can end halfway through a sample, and a chunk can be empty.
    Yield little-endian int16 bytes holding the samples decimate() gives for the whole stream,
    rounded and saturated like pcm.float_to_pcm16, each block as soon as it can be computed.
    Never yield an empty block: the recognizer reads an empty message as the end of the stream.
    """
    raise NotImplementedError
