"""Trial lists and the equal error rate (EER).

A trial pairs an enrollment utterance with a test utterance and says whether both come from
the same speaker. Real trial lists are long: VoxCeleb1-O has 37,720 trials.
"""
from __future__ import annotations

from dataclasses import dataclass

from .embed import cosine


@dataclass(frozen=True)
class Trial:
    enroll: str
    test: str
    target: bool


def parse_trials(text: str) -> list[Trial]:
    """Parse a VoxCeleb-style trial list.

    Each non-blank line is "<label> <enroll utterance> <test utterance>". Label 1 marks a
    target trial (same speaker), label 0 a non-target trial (different speakers).
    """
    trials = []
    for line in text.splitlines():
        if line.strip():
            label, enroll, test = line.split()
            trials.append(Trial(enroll, test, label == "1"))
    return trials


def score_trials(
    trials: list[Trial], embeddings: dict[str, list[float]]
) -> tuple[list[float], list[float]]:
    """Cosine-score every trial. Returns (target scores, non-target scores), each in trial order."""
    target: list[float] = []
    nontarget: list[float] = []
    for trial in trials:
        score = cosine(embeddings[trial.enroll], embeddings[trial.test])
        (target if trial.target else nontarget).append(score)
    return target, nontarget


def eer(target: list[float], nontarget: list[float]) -> tuple[float, float]:
    """Equal error rate, and the threshold where it is reached.

    A trial is accepted when its score is at or above the threshold. FAR is the fraction of
    non-target trials accepted, FRR the fraction of target trials rejected. The candidate
    thresholds are the observed scores; the EER threshold is the one where |FAR - FRR| is
    smallest (the lowest such threshold on a tie), and the EER is (FAR + FRR) / 2 there.
    Both lists must be non-empty.
    """
    if not target or not nontarget:
        raise ValueError("need at least one target and one non-target score")
    tg, nt = sorted(target), sorted(nontarget)
    s, d = len(tg), len(nt)
    i = j = 0  # at threshold t: tg[:i] are rejected, nt[j:] are accepted
    best: tuple[int, float, float] | None = None  # (|FAR - FRR| * s * d, EER, threshold)
    while i < s or j < d:
        t = tg[i] if j == d or (i < s and tg[i] <= nt[j]) else nt[j]
        gap = abs((d - j) * s - i * d)
        if best is None or gap < best[0]:
            best = (gap, ((d - j) / d + i / s) / 2, t)
        while i < s and tg[i] == t:  # scores equal to t are accepted at t, rejected above it
            i += 1
        while j < d and nt[j] == t:
            j += 1
    return best[1], best[2]
