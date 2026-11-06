"""k-nearest-neighbour tagging over the clip bank."""
from __future__ import annotations

import math

from .bank import ClipBank


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)


def classify(bank: ClipBank, features: list[float], k: int = 3) -> str:
    """Label features by majority vote over the k most similar train clips (cosine similarity).

    A tie between labels goes to the label whose votes have the larger summed similarity,
    then to the alphabetically first label.
    """
    raise NotImplementedError


def evaluate(bank: ClipBank, k: int = 3) -> dict:
    """Classify every eval clip against the train clips.

    Returns {"accuracy": float, "recall": {label: float}, "macro_f1": float}.
    recall and macro F1 cover every label that appears in the eval split.
    """
    raise NotImplementedError
