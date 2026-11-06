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
    train = bank.clips(split="train")
    if not train:
        raise ValueError("the bank has no train clips")
    if not 1 <= k <= len(train):
        raise ValueError(f"k must be between 1 and {len(train)}, got {k}")
    ranked = sorted(
        ((cosine(features, clip.features), i, clip.label) for i, clip in enumerate(train)),
        key=lambda item: (-item[0], item[1]),
    )
    votes: dict[str, list[float]] = {}
    for sim, _, label in ranked[:k]:
        tally = votes.setdefault(label, [0, 0.0])
        tally[0] += 1
        tally[1] += sim
    return min(votes, key=lambda label: (-votes[label][0], -votes[label][1], label))


def evaluate(bank: ClipBank, k: int = 3) -> dict:
    """Classify every eval clip against the train clips.

    Returns {"accuracy": float, "recall": {label: float}, "macro_f1": float}.
    recall and macro F1 cover every label that appears in the eval split.
    """
    eval_clips = bank.clips(split="eval")
    if not eval_clips:
        raise ValueError("the bank has no eval clips")
    gold = [clip.label for clip in eval_clips]
    pred = [classify(bank, clip.features, k) for clip in eval_clips]
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    for label in sorted(set(gold)):
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        r = tp / (tp + fn)
        prec = tp / (tp + fp) if tp + fp else 0.0
        recall[label] = r
        f1[label] = 2 * prec * r / (prec + r) if prec + r else 0.0
    return {
        "accuracy": sum(g == p for g, p in zip(gold, pred)) / len(gold),
        "recall": recall,
        "macro_f1": sum(f1.values()) / len(f1),
    }
