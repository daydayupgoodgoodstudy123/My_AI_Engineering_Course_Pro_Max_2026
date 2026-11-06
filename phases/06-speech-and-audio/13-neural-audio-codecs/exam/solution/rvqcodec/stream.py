"""Encode and decode a live stream, frame by frame."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .codec import Codec
from .quantize import rvq_decode, rvq_encode


@dataclass(frozen=True)
class Frame:
    """One frame on the wire.

    codes holds one code per codebook, codebook 0 (the semantic code) first; the network
    may drop trailing acoustic codes. length is how many of the frame's hop samples are
    real audio: hop, except for a zero-padded last frame.
    """

    index: int
    codes: tuple[int, ...]
    length: int


async def encode_stream(chunks: AsyncIterator[list[float]], codec: Codec) -> AsyncIterator[Frame]:
    """Encode audio as it arrives.

    Chunks can have any size, including zero. Yield each frame as soon as its last sample
    has arrived. When the stream ends, a partial frame is zero-padded, as Codec.encode
    does, and yielded with its real length.
    """
    buffer: list[float] = []
    index = 0
    async for chunk in chunks:
        buffer.extend(chunk)
        while len(buffer) >= codec.hop:
            yield _encode_frame(codec, index, buffer[: codec.hop], codec.hop)
            del buffer[: codec.hop]
            index += 1
    if buffer:
        length = len(buffer)
        yield _encode_frame(codec, index, buffer + [0.0] * (codec.hop - length), length)


def _encode_frame(codec: Codec, index: int, samples: list[float], length: int) -> Frame:
    codes = rvq_encode([samples], codec.codebooks)
    return Frame(index, tuple(row[0] for row in codes), length)


async def decode_stream(frames: AsyncIterator[Frame], codec: Codec) -> AsyncIterator[list[float]]:
    """Decode frames as they arrive: yield frame.length samples for every frame, without
    waiting for the next one.

    A frame that lost acoustic codes decodes from the codes it still has. A frame without
    its semantic code raises ValueError.
    """
    async for frame in frames:
        if not frame.codes:
            raise ValueError(f"frame {frame.index} has no semantic code")
        if len(frame.codes) > len(codec.codebooks):
            raise ValueError(f"frame {frame.index} has more codes than the codec has codebooks")
        (samples,) = rvq_decode([[code] for code in frame.codes], codec.codebooks)
        yield samples[: frame.length]
