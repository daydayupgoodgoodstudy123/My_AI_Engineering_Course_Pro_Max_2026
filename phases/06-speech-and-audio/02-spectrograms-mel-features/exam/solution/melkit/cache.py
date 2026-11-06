"""Feature matrices cached on disk, keyed by clip content and front-end config."""
from __future__ import annotations

import hashlib
import os
import struct
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path

_HEADER = struct.Struct("<4sII")  # magic, frames, features per frame
_MAGIC = b"MELK"


@dataclass(frozen=True)
class Features:
    """A feature matrix: one row per frame, n_feats values in every row."""

    n_feats: int
    frames: list[list[float]]

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.frames), self.n_feats)


def clip_hash(samples: list[float], sample_rate: int) -> str:
    """Hex content hash of a clip: its sample rate and the exact value of every sample."""
    digest = hashlib.sha256(struct.pack("<Q", sample_rate))
    digest.update(struct.pack(f"<{len(samples)}d", *samples))
    return digest.hexdigest()


class FeatureCache:
    """Feature matrices on disk under one directory, keyed by (clip hash, config fingerprint).

    get() returns exactly what put() stored, the same floats and the same shape, also after
    the cache is reopened. Nothing is kept in memory between calls.
    """

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, clip_id: str, config_id: str, feats: Features) -> None:
        """Store feats under (clip_id, config_id), replacing any earlier entry.

        Every row must hold exactly feats.n_feats values; otherwise raise ValueError and store nothing.
        """
        for i, row in enumerate(feats.frames):
            if len(row) != feats.n_feats:
                raise ValueError(f"row {i} has {len(row)} values, expected {feats.n_feats}")
        flat = array("d", [v for row in feats.frames for v in row])
        if sys.byteorder != "little":
            flat.byteswap()
        path = self._path(clip_id, config_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(_HEADER.pack(_MAGIC, len(feats.frames), feats.n_feats) + flat.tobytes())
        os.replace(tmp, path)

    def get(self, clip_id: str, config_id: str) -> Features | None:
        """The features stored under (clip_id, config_id), or None when there are none."""
        path = self._path(clip_id, config_id)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return None
        magic, n_frames, n_feats = _HEADER.unpack_from(data)
        flat = array("d")
        flat.frombytes(data[_HEADER.size :])
        if magic != _MAGIC or len(flat) != n_frames * n_feats:
            raise ValueError(f"cache entry {path.name} is corrupt")
        if sys.byteorder != "little":
            flat.byteswap()
        values = flat.tolist()
        return Features(n_feats, [values[i * n_feats : (i + 1) * n_feats] for i in range(n_frames)])

    def _path(self, clip_id: str, config_id: str) -> Path:
        name = hashlib.sha256(f"{clip_id}\0{config_id}".encode()).hexdigest()
        return self.root / f"{name}.feat"
