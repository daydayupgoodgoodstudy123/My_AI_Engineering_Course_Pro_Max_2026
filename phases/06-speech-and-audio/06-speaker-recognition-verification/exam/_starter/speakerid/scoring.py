"""Identity claims: S-norm scoring against an imposter cohort, and a threshold for a target FAR."""
from __future__ import annotations

from .embed import cosine
from .registry import SpeakerRegistry


def threshold_at_far(target: list[float], nontarget: list[float], target_far: float) -> float:
    """The lowest dev score whose FAR is at most target_far.

    FAR at threshold t is the fraction of non-target scores at or above t. Every dev score,
    target or non-target, is a candidate threshold. Raise ValueError when no candidate brings
    FAR down to target_far.
    """
    raise NotImplementedError


class Verifier:
    """Accept or reject claims that a test embedding comes from an enrolled speaker.

    The raw score of a claim is the cosine between the speaker's template and the test
    embedding. S-norm normalizes it twice against the cohort, a fixed list of imposter
    embeddings: once by the mean and population standard deviation of the template's cosines
    with the cohort, once by those of the test embedding's cosines with the cohort. The score is
    the average of the two. With top_k set (AS-norm), each side keeps only its own top_k
    highest cohort cosines.
    """

    def __init__(
        self, registry: SpeakerRegistry, cohort: list[list[float]], top_k: int | None = None
    ) -> None:
        if len(cohort) < 2:
            raise ValueError("the cohort needs at least two embeddings")
        if top_k is not None and not 2 <= top_k <= len(cohort):
            raise ValueError(f"top_k must be between 2 and {len(cohort)}")
        self.registry = registry
        self.cohort = cohort
        self.top_k = top_k
        self.threshold: float | None = None

    def score(self, speaker: str, embedding: list[float]) -> float:
        """S-normalized score of the claim that embedding was spoken by speaker."""
        raise NotImplementedError

    def calibrate(
        self, dev_trials: list[tuple[str, list[float], bool]], target_far: float
    ) -> float:
        """Choose, keep and return the decision threshold for a target false accept rate.

        dev_trials are (claimed speaker, test embedding, is target) from held-out data of the
        target domain. The threshold is threshold_at_far over their scores, on the same scale
        that verify compares against.
        """
        raise NotImplementedError

    def verify(self, speaker: str, embedding: list[float]) -> bool:
        """Accept the claim when its score is at or above the threshold. Call calibrate first."""
        raise NotImplementedError
