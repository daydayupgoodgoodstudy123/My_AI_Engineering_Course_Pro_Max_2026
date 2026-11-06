"""kNN-VC: voice conversion by nearest-neighbour regression over frame features.

Source and target are sequences of per-frame features (WavLM features in the real system).
Every source frame is replaced by frames the target speaker actually produced, so the content
follows the source while the voice comes from the target.
"""
from __future__ import annotations

import math


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)


def knn_convert(source: list[list[float]], matching: list[list[float]], k: int = 4) -> list[list[float]]:
    """Replace every source frame with the mean of its k nearest frames in the matching set.

    Nearest means the smallest cosine distance (1 - cosine similarity). Ties go to the frame
    that comes first in the matching set. The result has one frame per source frame and is
    built from matching frames only. k outside 1..len(matching) raises ValueError.
    """
    if not 1 <= k <= len(matching):
        raise ValueError(f"k must be between 1 and {len(matching)}, got {k}")
    out = []
    for frame in source:
        ranked = sorted(range(len(matching)), key=lambda j: -cosine(frame, matching[j]))
        nearest = [matching[j] for j in ranked[:k]]
        out.append([sum(column) / k for column in zip(*nearest)])
    return out
