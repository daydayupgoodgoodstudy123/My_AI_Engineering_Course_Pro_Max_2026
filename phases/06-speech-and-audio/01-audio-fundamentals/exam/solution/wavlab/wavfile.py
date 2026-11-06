"""WAV files for the archive: 16- or 24-bit PCM, any number of channels."""
from __future__ import annotations

import struct
from dataclasses import dataclass

PCM = 1
SAMPLE_WIDTHS = (2, 3)


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
    width = audio.sample_width
    if width not in SAMPLE_WIDTHS:
        raise ValueError(f"sample_width must be 2 or 3 bytes, got {width}")
    if not audio.channels or len({len(channel) for channel in audio.channels}) != 1:
        raise ValueError("need at least one channel, and all channels the same length")
    full = 1 << (8 * width - 1)
    data = b"".join(
        max(-full, min(full - 1, round(x * full))).to_bytes(width, "little", signed=True)
        for frame in zip(*audio.channels)
        for x in frame
    )
    n_channels = len(audio.channels)
    block_align = n_channels * width
    fmt = struct.pack(
        "<HHIIHH", PCM, n_channels, audio.sample_rate, audio.sample_rate * block_align, block_align, 8 * width
    )
    return _chunk(b"RIFF", b"WAVE" + _chunk(b"fmt ", fmt) + _chunk(b"data", data))


def decode_wav(blob: bytes) -> Audio:
    """Read a 16- or 24-bit PCM WAV file. Anything else raises ValueError.

    The Audio keeps the file's sample width, so encode_wav(decode_wav(blob)) == blob.
    """
    if len(blob) < 12 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    end = min(len(blob), 8 + struct.unpack_from("<I", blob, 4)[0])
    found: dict[bytes, bytes] = {}
    pos = 12
    while pos + 8 <= end:
        chunk_id = blob[pos : pos + 4]
        (size,) = struct.unpack_from("<I", blob, pos + 4)
        if pos + 8 + size > end:
            raise ValueError(f"chunk {chunk_id!r} runs past the end of the file")
        found.setdefault(chunk_id, blob[pos + 8 : pos + 8 + size])
        pos += 8 + size + size % 2
    fmt, data = found.get(b"fmt "), found.get(b"data")
    if fmt is None or data is None or len(fmt) < 16:
        raise ValueError("a WAV file needs a fmt chunk and a data chunk")
    tag, n_channels, sample_rate, _, block_align, bits = struct.unpack_from("<HHIIHH", fmt)
    width = bits // 8
    if tag != PCM or bits % 8 or width not in SAMPLE_WIDTHS or n_channels < 1 or block_align != n_channels * width:
        raise ValueError("only 16- and 24-bit PCM is supported")
    data = data[: len(data) - len(data) % block_align]
    full = 1 << (8 * width - 1)
    values = [int.from_bytes(data[i : i + width], "little", signed=True) / full for i in range(0, len(data), width)]
    return Audio(sample_rate, [values[c::n_channels] for c in range(n_channels)], width)


def _chunk(chunk_id: bytes, payload: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(payload)) + payload + b"\x00" * (len(payload) % 2)
