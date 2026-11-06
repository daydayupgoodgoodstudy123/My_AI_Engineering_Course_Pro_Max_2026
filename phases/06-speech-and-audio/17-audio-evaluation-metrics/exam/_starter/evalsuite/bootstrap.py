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
    raise NotImplementedError


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
    raise NotImplementedError
