"""Word error rate, the number the lesson says to report."""
from __future__ import annotations

from collections.abc import Sequence


def edit_distance(ref: Sequence[str], hyp: Sequence[str]) -> int:
    """Fewest substitutions, deletions and insertions that turn ref into hyp.

    Runs in O(len(ref) * len(hyp)) time and handles transcripts of any length.
    """

    def dist(i: int, j: int) -> int:
        if i == 0:
            return j
        if j == 0:
            return i
        cost = 0 if ref[i - 1] == hyp[j - 1] else 1
        return min(dist(i - 1, j) + 1, dist(i, j - 1) + 1, dist(i - 1, j - 1) + cost)

    return dist(len(ref), len(hyp))


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate (S + D + I) / N, where N is the number of reference words.

    Words are split on whitespace and compared exactly, so normalize text before scoring.
    An empty reference raises ValueError.
    """
    ref, hyp = reference.split(), hypothesis.split()
    if not ref:
        raise ValueError("WER needs at least one reference word")
    return edit_distance(ref, hyp) / len(hyp)
