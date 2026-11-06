"""Paired bootstrap: is one system's lower error rate more than the luck of the test set?"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Comparison:
    delta: float  # candidate rate minus baseline rate on the whole test set
    ci: tuple[float, float]  # percentile interval of delta over the bootstrap replicates
    p_better: float  # share of replicates in which the candidate makes fewer errors


def percentile_interval(values: list[float], confidence: float = 0.95) -> tuple[float, float]:
    """Central interval of bootstrap replicates.

    With B values and k = round(B * (1 - confidence) / 2), drop the k smallest and the k largest;
    the interval runs from the smallest to the largest value left. Values may come in any order.
    """
    if not values:
        raise ValueError("no replicates")
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be between 0 and 1, got {confidence}")
    ordered = sorted(values)
    k = round(len(ordered) * (1 - confidence) / 2)
    return ordered[k], ordered[len(ordered) - 1 - k]


def paired_bootstrap(
    baseline: dict[str, tuple[int, int]],
    candidate: dict[str, tuple[int, int]],
    replicates: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
) -> Comparison:
    """Compare two systems on the same test set by paired bootstrap resampling.

    baseline and candidate map utterance id -> (errors, reference units), as error_counts gives.
    They must cover the same utterances with the same reference units, or ValueError. The rate
    of a system on some utterances is its summed errors over their summed units, and
    delta = candidate rate - baseline rate, so a negative delta favours the candidate.
    Each replicate draws as many utterances as the test set holds, with replacement, indexing
    into the sorted list of ids, and scores both systems on that same draw. The draws come from
    random.Random(seed), never from the global random state.
    Returns the delta on the whole test set, percentile_interval of the replicate deltas, and
    p_better, the share of replicates whose delta is below zero.
    """
    if baseline.keys() != candidate.keys():
        raise ValueError("the two runs cover different utterances")
    if not baseline:
        raise ValueError("the test set is empty")
    if replicates < 1:
        raise ValueError("need at least one replicate")
    ids = sorted(baseline)
    for utterance in ids:
        if baseline[utterance][1] != candidate[utterance][1]:
            raise ValueError(f"{utterance!r} has different reference lengths in the two runs")
    units = [baseline[u][1] for u in ids]
    base = [baseline[u][0] for u in ids]
    cand = [candidate[u][0] for u in ids]

    def delta(draw: list[int]) -> float:
        total = sum(units[i] for i in draw)
        return sum(cand[i] for i in draw) / total - sum(base[i] for i in draw) / total

    rng = random.Random(seed)
    n = len(ids)
    deltas = [delta([rng.randrange(n) for _ in range(n)]) for _ in range(replicates)]
    return Comparison(
        delta(list(range(n))),
        percentile_interval(deltas, confidence),
        sum(d < 0 for d in deltas) / replicates,
    )
