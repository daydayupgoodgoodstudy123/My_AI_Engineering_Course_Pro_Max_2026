"""Glue used by the eval jobs: score runs, compare them, publish them, report progress."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .board import Entry, Leaderboard
from .bootstrap import Comparison, paired_bootstrap
from .scoring import CHARACTER_LANGUAGES, NORMALIZER, error_counts
from .stream import Scored, stream_report

Run = dict[str, str]  # utterance id -> transcript


class EvalService:
    def __init__(self, board: Leaderboard, replicates: int = 1000, seed: int = 0) -> None:
        self.board = board
        self.replicates = replicates
        self.seed = seed

    def score_run(
        self, references: Run, hypotheses: Run, language: str
    ) -> dict[str, tuple[int, int]]:
        """(errors, reference units) per utterance.

        An utterance the system returned nothing for is scored against an empty hypothesis,
        so a failed decode counts as every unit deleted rather than dropping out of the score.
        """
        return {
            utterance: error_counts(reference, hypotheses.get(utterance, ""), language)
            for utterance, reference in references.items()
        }

    def compare(self, references: Run, baseline: Run, candidate: Run, language: str) -> Comparison:
        """Paired bootstrap of two runs over the same references."""
        return paired_bootstrap(
            self.score_run(references, baseline, language),
            self.score_run(references, candidate, language),
            self.replicates,
            self.seed,
        )

    def publish(
        self, model: str, benchmark: str, references: Run, hypotheses: Run, language: str
    ) -> Entry:
        """Score a run and put its WER (CER for character languages) on the board.

        The interval comes from comparing the run with a system that makes no errors, whose
        delta is the run's own error rate.
        """
        run = self.score_run(references, hypotheses, language)
        perfect = {utterance: (0, units) for utterance, (_, units) in run.items()}
        spread = paired_bootstrap(perfect, run, self.replicates, self.seed)
        metric = "cer" if language in CHARACTER_LANGUAGES else "wer"
        self.board.submit(model, benchmark, metric, spread.delta, len(run), spread.ci, NORMALIZER)
        return self.board.get(model, benchmark, metric)

    def progress(
        self,
        batches: AsyncIterator[list[tuple[str, str, str, str]]],
        language: str,
        every: int = 100,
    ) -> AsyncIterator[str]:
        """Stream a running report for batches of (utterance, domain, reference, hypothesis)."""

        async def scored() -> AsyncIterator[list[Scored]]:
            async for batch in batches:
                yield [
                    Scored(utterance, domain, *error_counts(reference, hypothesis, language))
                    for utterance, domain, reference, hypothesis in batch
                ]

        return stream_report(scored(), every)
