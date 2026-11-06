"""Word lattices: the best transcripts through a DAG of scored word arcs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Arc:
    src: int
    dst: int
    word: str | None  # None for an arc that carries no word (silence, epsilon)
    am: float  # acoustic log-likelihood
    lm: float = 0.0  # language-model log-probability


def nbest(
    arcs: list[Arc], start: int, end: int, n: int, lm_weight: float = 1.0
) -> list[tuple[str, float]]:
    """The n best distinct transcripts from start to end, best first.

    A path scores the sum of am + lm_weight * lm over its arcs; an arc without a word adds
    its score but no word. When several paths spell the same transcript, the best of them
    counts. Equal scores are ordered by transcript. A cycle anywhere in the lattice raises
    ValueError, and so does a lattice with no path from start to end. The work grows with
    the number of arcs times n, not with the number of paths.
    """
    raise NotImplementedError


def best_path(arcs: list[Arc], start: int, end: int, lm_weight: float = 1.0) -> tuple[str, float]:
    """The single best transcript and its score."""
    return nbest(arcs, start, end, 1, lm_weight)[0]
