"""Mimi's timebase, and a toy stand-in for its encoder.

Mimi codes 24 kHz audio at 12.5 frames per second, 8 codes per 80 ms frame: codebook 0 is
semantic (what is being said), codebooks 1-7 are acoustic (how it sounds).
"""
from __future__ import annotations

from .tokens import CODEBOOK_SIZE, CODEBOOKS

SAMPLE_RATE = 24_000
FRAME_RATE = 12.5
FRAME_MS = 80
SAMPLES_PER_FRAME = SAMPLE_RATE / FRAME_RATE


def split_frames(pcm: list[float]) -> list[list[float]]:
    """Cut audio into whole frames of SAMPLES_PER_FRAME samples. A trailing partial frame is dropped."""
    count = len(pcm) // SAMPLES_PER_FRAME
    return [pcm[i * SAMPLES_PER_FRAME : (i + 1) * SAMPLES_PER_FRAME] for i in range(count)]


def encode_frame(frame: list[float]) -> list[int]:
    """Toy codes for one frame, codebook 0 first.

    Codebook 0 comes from the zero-crossing count (a crude "what"), codebooks 1-7 from the peak
    level of seven consecutive slices of the frame (a crude "how").
    """
    crossings = sum((a < 0.0) != (b < 0.0) for a, b in zip(frame, frame[1:]))
    codes = [min(crossings, CODEBOOK_SIZE - 1)]
    size = len(frame) // (CODEBOOKS - 1)
    for k in range(CODEBOOKS - 1):
        peak = max(abs(x) for x in frame[k * size : (k + 1) * size])
        codes.append(min(int(peak * CODEBOOK_SIZE), CODEBOOK_SIZE - 1))
    return codes


def encode(pcm: list[float]) -> list[list[int]]:
    """Encode the whole frames of a clip.

    Returns codebook-major codes, codes[k][t] for codebook k of frame t: the layout of Mimi's
    (n_q, T) code tensor.
    """
    per_frame = [encode_frame(frame) for frame in split_frames(pcm)]
    return [[codes[k] for codes in per_frame] for k in range(CODEBOOKS)]


def frames_of(codes: list[list[int]]) -> list[list[int]]:
    """Frame-major copy of codebook-major codes: frames_of(codes)[t][k] == codes[k][t]."""
    return [list(frame) for frame in zip(*codes)]
