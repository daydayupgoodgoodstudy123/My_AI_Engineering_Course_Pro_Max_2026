"""Encode and decode a live stream, frame by frame."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .codec import Codec


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
    raise NotImplementedError


async def decode_stream(frames: AsyncIterator[Frame], codec: Codec) -> AsyncIterator[list[float]]:
    """Decode frames as they arrive: yield frame.length samples for every frame, without
    waiting for the next one.

    A frame that lost acoustic codes decodes from the codes it still has. A frame without
    its semantic code raises ValueError.
    """
    raise NotImplementedError
