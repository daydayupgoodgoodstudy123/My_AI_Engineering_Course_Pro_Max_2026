"""The before/after comparison: the two pipelines compared run by run."""
from __future__ import annotations

from collections.abc import Iterable

from .artifacts import PIPELINES
from .outcomes import HANDOFF_LEVELS, OUTCOMES, Outcome


def compare(records: Iterable[tuple[str, str, Outcome]]) -> dict:
    """Compare the two pipelines run by run.

    records are (run_id, pipeline, outcome) in any order, at most one per run and pipeline. A run
    is paired when it has a prompt-only and a workbench-guided outcome. Only paired runs are
    compared; the others are listed under "unpaired", in the order they first appear.

    Each outcome is compared as a number: the two flags as 1 and 0, files_outside_scope as how
    many files, handoff_quality as its level (missing 0 < partial 1 < full packet 2), and
    reviewer_total as it is. More is better, except for files_outside_scope, where fewer is.

    Returns {"n": paired runs, "unpaired": [...], "outcomes": {name: {"workbench": w,
    "prompt_only": p, "tie": t, "median_delta": d}}, "no_gain": [...]}: w, p and t count the
    paired runs where the workbench did better, prompt-only did better, or neither did; d is the
    median over paired runs of (workbench number minus prompt-only number). "no_gain" lists the
    paired runs, in order, where the workbench did better on no outcome; a report shows them
    instead of hiding them. Raises ValueError when no run is paired.
    """
    raise NotImplementedError
