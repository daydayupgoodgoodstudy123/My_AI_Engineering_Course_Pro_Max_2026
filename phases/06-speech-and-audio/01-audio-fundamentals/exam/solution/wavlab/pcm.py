"""16-bit PCM samples and the floats the rest of WavLab works with.

WAV files store 16-bit audio as signed little-endian integers, one frame after another;
a stereo frame is a left sample followed by a right sample (L0 R0 L1 R1 ...).
Reading divides by 32768, the convention soundfile and torchaudio use, so -32768 becomes
-1.0 and 32767 becomes 32767/32768. Writing is the exact inverse.
"""
from __future__ import annotations

import struct


def pcm16_to_float(value: int) -> float:
    """One int16 sample as a float in [-1.0, 1.0)."""
    return value / 32768


def float_to_pcm16(x: float) -> int:
    """One float sample as int16: scale by 32768, round to the nearest integer, saturate.

    Out-of-range input clips to -32768 or 32767. Every value pcm16_to_float returns
    converts back to the integer it came from.
    """
    return max(-32768, min(32767, round(x * 32768)))


def decode_pcm16(raw: bytes, n_channels: int) -> list[list[float]]:
    """Interleaved little-endian int16 frames -> one list of floats per channel."""
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    return [[pcm16_to_float(v) for v in values[c::n_channels]] for c in range(n_channels)]


def encode_pcm16(channels: list[list[float]]) -> bytes:
    """Equal-length channels -> interleaved little-endian int16 frames."""
    ints = [float_to_pcm16(x) for frame in zip(*channels) for x in frame]
    return struct.pack(f"<{len(ints)}h", *ints)
