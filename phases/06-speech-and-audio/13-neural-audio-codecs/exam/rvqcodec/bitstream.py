"""The codec's bitstream: one encoded clip as bytes."""
from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"RVQ1"
# magic, sample_rate, hop, codebook_size, n_q (number of codebooks), n_samples
HEADER = struct.Struct(">4sIIIBI")


@dataclass(frozen=True)
class Packet:
    """One encoded clip: codes[q][t] and what a decoder needs to play them back.

    The clip had n_samples samples, cut into frames of hop samples; the last frame is
    zero-padded, so every row of codes holds ceil(n_samples / hop) codes. Every codebook
    has codebook_size codewords.
    """

    sample_rate: int
    hop: int
    codebook_size: int
    n_samples: int
    codes: list[list[int]]

    @property
    def frame_rate(self) -> float:
        """Frames per second."""
        raise NotImplementedError

    @property
    def bits_per_code(self) -> int:
        """Bits that one code takes in the bitstream (no entropy coding)."""
        raise NotImplementedError

    @property
    def bitrate(self) -> float:
        """Bits per second."""
        raise NotImplementedError


def pack(packet: Packet) -> bytes:
    """HEADER, then the codes bit-packed.

    Codes go frame by frame, and within a frame codebook 0 (the semantic code) comes
    first. Each code takes bits_per_code bits, most significant bit first, and the last
    byte is padded with zero bits. A code outside the codebook, or a row of the wrong
    length, raises ValueError.
    """
    raise NotImplementedError


def unpack(data: bytes) -> Packet:
    """Read a packet written by pack. Raises ValueError for anything that is not a whole packet."""
    raise NotImplementedError
