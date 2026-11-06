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
        return self.sample_rate / self.hop

    @property
    def bits_per_code(self) -> int:
        """Bits that one code takes in the bitstream (no entropy coding)."""
        return (self.codebook_size - 1).bit_length()

    @property
    def bitrate(self) -> float:
        """Bits per second."""
        return self.frame_rate * len(self.codes) * self.bits_per_code


def _n_frames(n_samples: int, hop: int) -> int:
    return -(-n_samples // hop)


def pack(packet: Packet) -> bytes:
    """HEADER, then the codes bit-packed.

    Codes go frame by frame, and within a frame codebook 0 (the semantic code) comes
    first. Each code takes bits_per_code bits, most significant bit first, and the last
    byte is padded with zero bits. A code outside the codebook, or a row of the wrong
    length, raises ValueError.
    """
    n_frames = _n_frames(packet.n_samples, packet.hop)
    if any(len(row) != n_frames for row in packet.codes):
        raise ValueError(f"every row of codes needs {n_frames} codes, one per frame")
    bits = packet.bits_per_code
    value = 0
    for t in range(n_frames):
        for row in packet.codes:
            code = row[t]
            if not 0 <= code < packet.codebook_size:
                raise ValueError(f"code {code} is outside a {packet.codebook_size}-entry codebook")
            value = (value << bits) | code
    n_bits = n_frames * len(packet.codes) * bits
    pad = -n_bits % 8
    header = HEADER.pack(
        MAGIC, packet.sample_rate, packet.hop, packet.codebook_size, len(packet.codes), packet.n_samples
    )
    return header + (value << pad).to_bytes((n_bits + pad) // 8, "big")


def unpack(data: bytes) -> Packet:
    """Read a packet written by pack. Raises ValueError for anything that is not a whole packet."""
    if len(data) < HEADER.size:
        raise ValueError(f"a packet starts with a {HEADER.size}-byte header, got {len(data)} bytes")
    magic, sample_rate, hop, codebook_size, n_q, n_samples = HEADER.unpack_from(data)
    if magic != MAGIC:
        raise ValueError(f"not an RVQ packet: magic {magic!r}")
    n_frames = _n_frames(n_samples, hop)
    bits = (codebook_size - 1).bit_length()
    n_bits = n_frames * n_q * bits
    payload = data[HEADER.size :]
    if len(payload) != (n_bits + 7) // 8:
        raise ValueError(f"{n_frames} frames need {(n_bits + 7) // 8} payload bytes, got {len(payload)}")
    value = int.from_bytes(payload, "big") >> (-n_bits % 8)
    mask = (1 << bits) - 1
    flat = [(value >> (n_bits - bits * (i + 1))) & mask for i in range(n_frames * n_q)]
    codes = [flat[q::n_q] for q in range(n_q)]
    return Packet(sample_rate, hop, codebook_size, n_samples, codes)
