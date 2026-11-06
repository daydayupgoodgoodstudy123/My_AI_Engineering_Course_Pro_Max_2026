"""The chunk tree inside a RIFF file (WAV, AVI, WebP, ...)."""
from __future__ import annotations

CONTAINERS = (b"RIFF", b"LIST")


def walk(blob: bytes) -> list[tuple[str, int, int]]:
    """Every chunk of a RIFF file, depth first in file order, as (path, offset, size).

    A chunk is a 4-byte id, a little-endian uint32 size and that many bytes of payload, plus
    one zero pad byte when the size is odd. RIFF and LIST chunks are containers: their payload
    is a 4-byte type followed by child chunks, and a path names them "id:type", as in
    "RIFF:WAVE/LIST:INFO/INAM". Every other chunk is a leaf, whatever its payload holds.
    offset is where the chunk's payload starts in blob; size is the size in its header.

    A chunk that runs past the end of its parent raises ValueError, and so does a blob that
    does not start with a RIFF chunk. The last chunk in a parent may be missing its pad byte
    (the stdlib wave module leaves it out).
    """
    raise NotImplementedError


def info_tags(blob: bytes) -> dict[str, str]:
    """Text tags from the LIST:INFO chunks directly inside the RIFF chunk, e.g. {"INAM": "Title"}.

    Values are UTF-8 with their trailing NUL bytes removed.
    """
    raise NotImplementedError
