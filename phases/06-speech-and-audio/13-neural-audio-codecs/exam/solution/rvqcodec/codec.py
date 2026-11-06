"""Glue used by the API layer: a toy codec around the RVQ bottleneck."""
from __future__ import annotations

from .bitstream import Packet, pack, unpack
from .quantize import rvq_decode, rvq_encode


class Codec:
    """A toy RVQ codec.

    The "encoder" cuts audio into frames of hop samples (one frame is one latent vector),
    residual VQ turns every frame into one code per codebook, and the "decoder" adds the
    chosen codewords back up and lays the frames end to end. Codebook 0 plays the part of
    Mimi's semantic codebook; the later codebooks carry acoustic detail.
    """

    def __init__(self, sample_rate: int, hop: int, codebooks: list[list[list[float]]]) -> None:
        if not codebooks or any(len(codeword) != hop for book in codebooks for codeword in book):
            raise ValueError("need at least one codebook, and every codeword must be hop samples long")
        self.sample_rate = sample_rate
        self.hop = hop
        self.codebooks = codebooks

    @property
    def codebook_size(self) -> int:
        return len(self.codebooks[0])

    def frames(self, signal: list[float]) -> list[list[float]]:
        """Cut a clip into frames of hop samples, zero-padding the last partial frame."""
        frames = [list(signal[i : i + self.hop]) for i in range(0, len(signal), self.hop)]
        if frames and len(frames[-1]) < self.hop:
            frames[-1] += [0.0] * (self.hop - len(frames[-1]))
        return frames

    def encode(self, signal: list[float]) -> Packet:
        codes = rvq_encode(self.frames(signal), self.codebooks)
        return Packet(self.sample_rate, self.hop, self.codebook_size, len(signal), codes)

    def decode(self, packet: Packet) -> list[float]:
        """Rebuild the clip from its codes, cut back to its original length."""
        frames = rvq_decode(packet.codes, self.codebooks)
        return [sample for frame in frames for sample in frame][: packet.n_samples]

    def compress(self, signal: list[float]) -> bytes:
        return pack(self.encode(signal))

    def decompress(self, data: bytes) -> list[float]:
        """Decode bytes written by compress.

        A packet made at another sample rate, hop or codebook size, or with more codebooks
        than this codec has, raises ValueError: decoding it anyway would play the wrong audio
        without any error.
        """
        packet = unpack(data)
        made = (packet.sample_rate, packet.hop, packet.codebook_size)
        if made != (self.sample_rate, self.hop, self.codebook_size):
            raise ValueError(
                f"packet was made at {packet.sample_rate} Hz, hop {packet.hop}, {packet.codebook_size} codes;"
                f" this codec is {self.sample_rate} Hz, hop {self.hop}, {self.codebook_size} codes"
            )
        if len(packet.codes) > len(self.codebooks):
            raise ValueError(f"packet has {len(packet.codes)} codebooks, this codec has {len(self.codebooks)}")
        return self.decode(packet)
