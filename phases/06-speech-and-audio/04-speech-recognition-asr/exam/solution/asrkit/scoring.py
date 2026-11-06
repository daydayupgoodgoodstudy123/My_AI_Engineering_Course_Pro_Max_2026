"""Word error rate, the number the lesson says to report."""
from __future__ import annotations

from collections.abc import Sequence


def edit_distance(ref: Sequence[str], hyp: Sequence[str]) -> int:
    """Fewest substitutions, deletions and insertions that turn ref into hyp.

    Runs in O(len(ref) * len(hyp)) time and handles transcripts of any length.
    """
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate (S + D + I) / N, where N is the number of reference words.

    Words are split on whitespace and compared exactly, so normalize text before scoring.
    An empty reference raises ValueError.
    """
    ref, hyp = reference.split(), hypothesis.split()
    if not ref:
        raise ValueError("WER needs at least one reference word")
    return edit_distance(ref, hyp) / len(ref)
