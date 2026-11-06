"""Word lattices: the best transcripts through a DAG of scored word arcs."""
from __future__ import annotations

from collections import defaultdict, deque
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
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    leaving: dict[int, list[Arc]] = defaultdict(list)
    waiting: dict[int, int] = defaultdict(int)  # incoming arcs not followed yet
    nodes = {start, end}
    for arc in arcs:
        leaving[arc.src].append(arc)
        waiting[arc.dst] += 1
        nodes.update((arc.src, arc.dst))
    ready = deque(sorted(node for node in nodes if waiting[node] == 0))
    order: list[int] = []
    while ready:
        node = ready.popleft()
        order.append(node)
        for arc in leaving[node]:
            waiting[arc.dst] -= 1
            if waiting[arc.dst] == 0:
                ready.append(arc.dst)
    if len(order) < len(nodes):
        raise ValueError("the lattice has a cycle")

    # node -> (words so far, score) for the paths that have reached it
    reached: dict[int, list[tuple[tuple[str, ...], float]]] = {start: [((), 0.0)]}
    for node in order:
        paths = reached.pop(node, None)
        if not paths:
            continue
        top = _best_distinct(paths, n)
        if node == end:
            return [(" ".join(words), score) for words, score in top]
        for arc in leaving[node]:
            step = arc.am + lm_weight * arc.lm
            extra = () if arc.word is None else (arc.word,)
            arriving = reached.setdefault(arc.dst, [])
            arriving.extend((words + extra, score + step) for words, score in top)
    raise ValueError(f"no path from {start} to {end}")


def _best_distinct(
    paths: list[tuple[tuple[str, ...], float]], n: int
) -> list[tuple[tuple[str, ...], float]]:
    """The n best paths, keeping only the best one for each word sequence."""
    best: dict[tuple[str, ...], float] = {}
    for words, score in paths:
        if words not in best or score > best[words]:
            best[words] = score
    return sorted(best.items(), key=lambda item: (-item[1], " ".join(item[0])))[:n]


def best_path(arcs: list[Arc], start: int, end: int, lm_weight: float = 1.0) -> tuple[str, float]:
    """The single best transcript and its score."""
    return nbest(arcs, start, end, 1, lm_weight)[0]
