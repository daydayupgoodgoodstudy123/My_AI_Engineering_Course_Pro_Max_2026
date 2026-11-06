"""WAV files for the archive: 16- or 24-bit PCM, any number of channels."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Audio:
    sample_rate: int
    channels: list[list[float]]  # one list of samples per channel, all the same length
    sample_width: int = 2  # bytes per sample: 2 for 16-bit, 3 for 24-bit


def encode_wav(audio: Audio) -> bytes:
    """The PCM WAV file for audio, the same bytes the stdlib wave module writes.

    Layout, little-endian: "RIFF", the RIFF size, "WAVE", then a 16-byte "fmt " chunk packed as
    "<HHIIHH" (format 1 = PCM, channels, sample rate, bytes per second, bytes per frame, bits per
    sample), then a "data" chunk with the frames interleaved. A sample is scaled by
    2 ** (bits - 1), rounded and saturated, like pcm.float_to_pcm16.

    RIFF chunks are word aligned: a chunk with an odd size is followed by one zero pad byte,
    which its own size does not count and the size of the chunk around it does. The wave
    module leaves that pad byte out; the archive writes it.

    Channels of different lengths and sample widths other than 2 or 3 raise ValueError.
    """
    raise NotImplementedError


def decode_wav(blob: bytes) -> Audio:
    """Read a 16- or 24-bit PCM WAV file. Anything else raises ValueError.

    The Audio keeps the file's sample width, so encode_wav(decode_wav(blob)) == blob.
    """
    raise NotImplementedError
