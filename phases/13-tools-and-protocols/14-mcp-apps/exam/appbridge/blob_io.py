"""Given raw HTML storage: preserve bytes, check digests and repair damaged blobs."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def store_html(blobs: Path, text: str) -> str:
    """Store the exact UTF-8 HTML bytes once; repair a different existing blob."""
    data = text.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    if _blob(blobs, digest) != data:
        _write(blobs / digest, data)
    return digest


def load_html(blobs: Path, digest: str) -> str | None:
    """Return exact HTML only when its bytes match digest; a missing/damaged blob is a miss."""
    data = _blob(blobs, digest)
    if data is None or hashlib.sha256(data).hexdigest() != digest:
        return None
    return data.decode("utf-8")


def _blob(blobs: Path, digest: str) -> bytes | None:
    try:
        return (blobs / digest).read_bytes()
    except FileNotFoundError:
        return None


def _write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
