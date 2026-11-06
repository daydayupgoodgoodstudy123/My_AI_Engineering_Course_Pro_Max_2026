"""The chunk tree inside a RIFF file (WAV, AVI, WebP, ...)."""
from __future__ import annotations

import struct

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
    if blob[:4] != b"RIFF":
        raise ValueError("not a RIFF file")
    out: list[tuple[str, int, int]] = []
    _read_chunk(blob, 0, len(blob), "", out)
    return out


def _read_chunk(blob: bytes, pos: int, end: int, prefix: str, out: list) -> int:
    """Record the chunk at pos and everything inside it; return where the next chunk starts."""
    if pos + 8 > end:
        raise ValueError(f"truncated chunk header at byte {pos}")
    chunk_id = blob[pos : pos + 4]
    (size,) = struct.unpack_from("<I", blob, pos + 4)
    start, stop = pos + 8, pos + 8 + size
    if stop > end:
        raise ValueError(f"chunk {chunk_id!r} at byte {pos} runs past the end of its parent")
    name = prefix + chunk_id.decode("latin-1")
    if chunk_id in CONTAINERS:
        if size < 4:
            raise ValueError(f"container {chunk_id!r} at byte {pos} has no type")
        name += ":" + blob[start : start + 4].decode("latin-1")
        out.append((name, start, size))
        child = start + 4
        while child < stop:
            child = _read_chunk(blob, child, stop, name + "/", out)
    else:
        out.append((name, start, size))
    return stop + size % 2


def info_tags(blob: bytes) -> dict[str, str]:
    """Text tags from the LIST:INFO chunks directly inside the RIFF chunk, e.g. {"INAM": "Title"}.

    Values are UTF-8 with their trailing NUL bytes removed.
    """
    tags: dict[str, str] = {}
    for path, offset, size in walk(blob):
        parts = path.split("/")
        if len(parts) == 3 and parts[1] == "LIST:INFO":
            tags[parts[2]] = blob[offset : offset + size].rstrip(b"\x00").decode("utf-8")
    return tags
