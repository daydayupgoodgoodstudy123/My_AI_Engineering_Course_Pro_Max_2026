"""Feature matrices cached on disk, keyed by clip content and front-end config."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    raise NotImplementedError


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
        raise NotImplementedError

    def get(self, clip_id: str, config_id: str) -> Features | None:
        """The features stored under (clip_id, config_id), or None when there are none."""
        raise NotImplementedError
