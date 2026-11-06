"""Glue used by the audit API: what to add next, judged on a repo's latest audit."""
from __future__ import annotations

from .catch import Failure, catch_matrix
from .scorecard import Scorecard


class WorkbenchService:
    def __init__(self, scorecard: Scorecard) -> None:
        self.scorecard = scorecard

    def next_surfaces(self, repo: str, failures: list[Failure]) -> list[str]:
        """The surfaces to add next for repo, judged on its latest audit.

        Only surfaces scored 2 (healthy) count as present; partial, missing and refused
        surfaces do not.
        """
        history = self.scorecard.history(repo)
        if not history:
            raise LookupError(f"no audit of {repo!r}")
        latest = history[-1]
        present = [surface for surface, score in latest.scores.items() if score == 2]
        return catch_matrix(failures, present).next_surfaces
