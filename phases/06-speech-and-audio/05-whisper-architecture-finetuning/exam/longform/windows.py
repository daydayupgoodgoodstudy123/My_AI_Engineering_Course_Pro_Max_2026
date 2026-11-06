"""Whisper's fixed 30 s input window.

How many samples, mel frames and encoder positions one window holds, and the plan of
overlapping windows that covers a longer recording.
"""
from __future__ import annotations

from typing import NamedTuple

SAMPLE_RATE = 16_000                  # Whisper hears 16 kHz mono
N_FFT = 400                           # 25 ms STFT window
HOP_LENGTH = 160                      # 10 ms hop: 100 mel frames per second
CHUNK_S = 30                          # one window is 30 s of audio
N_SAMPLES = CHUNK_S * SAMPLE_RATE     # 480,000 samples
N_FRAMES = N_SAMPLES // HOP_LENGTH    # 3,000 mel frames
N_POSITIONS = N_FRAMES // 2           # 1,500 encoder positions, 0.02 s each


class Window(NamedTuple):
    """One decoder call: samples start:end of the recording, padded to 30 s."""

    start: int
    end: int
    frames: int      # mel frames of real audio; the rest of the 3,000 are padding
    positions: int   # encoder positions of real audio; the rest of the 1,500 are padding


def mel_frames(n_samples: int) -> int:
    """Mel frames of real audio when a window holds n_samples samples.

    Whisper's STFT is centered and its last frame is dropped, so the count is
    n_samples // HOP_LENGTH: a full window is exactly N_FRAMES.
    """
    if not 0 <= n_samples <= N_SAMPLES:
        raise ValueError(f"a window holds 0 to {N_SAMPLES} samples, got {n_samples}")
    return 1 + (n_samples - N_FFT) // HOP_LENGTH


def encoder_positions(n_frames: int) -> int:
    """Encoder positions that see real audio.

    The encoder's second conv has kernel 3, stride 2 and padding 1, so n frames come out
    as ceil(n / 2) positions and a full window as N_POSITIONS.
    """
    if not 0 <= n_frames <= N_FRAMES:
        raise ValueError(f"a window holds 0 to {N_FRAMES} mel frames, got {n_frames}")
    return n_frames // 2


def plan_windows(n_samples: int, overlap_s: float = 5.0) -> list[Window]:
    """Cover a recording of n_samples samples with 30 s windows that overlap by overlap_s.

    Window k starts k * (30 - overlap_s) seconds in. The last window is the first one that
    reaches the end of the recording, and it stops there, so it can be shorter than 30 s
    (Whisper pads it). Every sample is covered and no window lies inside another. A
    recording of 30 s or less is one window.
    """
    if n_samples < 1:
        raise ValueError("an empty recording has no windows")
    overlap = round(overlap_s * SAMPLE_RATE)
    if not 0 <= overlap < N_SAMPLES:
        raise ValueError(f"overlap_s must be at least 0 and under {CHUNK_S} s, got {overlap_s}")
    windows: list[Window] = []
    for start in range(0, n_samples, N_SAMPLES - overlap):
        end = min(start + N_SAMPLES, n_samples)
        if any(w.start <= start and end <= w.end for w in windows):
            continue
        frames = mel_frames(end - start)
        windows.append(Window(start, end, frames, encoder_positions(frames)))
    return windows
