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
            trials.append(Trial(enroll, test, bool(label)))
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
    thresholds = sorted(set(target + nontarget))
    best = (1.0, 1.0, 0.0)  # (fa, fr, threshold)
    for t in thresholds:
        fr = sum(1 for s in target if s < t) / len(target)
        fa = sum(1 for s in nontarget if s >= t) / len(nontarget)
        if abs(fa - fr) < abs(best[0] - best[1]):
            best = (fa, fr, t)
    return (best[0] + best[1]) / 2, best[2]
