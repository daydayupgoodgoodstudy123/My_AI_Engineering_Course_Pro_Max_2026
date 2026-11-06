"""Speaker embeddings from an upstream model (ECAPA-TDNN, WavLM-SV): normalization and cosine."""
from __future__ import annotations

import math


def l2_normalize(v: list[float]) -> list[float]:
    """Scale v to unit length. The zero vector has no direction and comes back as zeros."""
    norm = math.sqrt(sum(x * x for x in v)) or 1e-12
    return [x / norm for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two embeddings of any norm; 0.0 if either one is the zero vector."""
    return sum(x * y for x, y in zip(a, b))
