"""The before/after comparison: the two pipelines compared run by run."""
from __future__ import annotations

import statistics
from collections.abc import Iterable

from .artifacts import PIPELINES
from .outcomes import HANDOFF_LEVELS, OUTCOMES, Outcome

FEWER_IS_BETTER = {"files_outside_scope"}


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
    by_run: dict[str, dict[str, Outcome]] = {}
    for run_id, pipeline, outcome in records:
        if pipeline not in PIPELINES:
            raise ValueError(f"unknown pipeline {pipeline!r}")
        by_run.setdefault(run_id, {})[pipeline] = outcome
    paired = [
        (run_id, got["prompt-only"], got["workbench-guided"])
        for run_id, got in by_run.items()
        if len(got) == len(PIPELINES)
    ]
    if not paired:
        raise ValueError("no run has both pipelines, so there is nothing to compare")
    gained = {run_id: False for run_id, _, _ in paired}
    outcomes = {}
    for name in OUTCOMES:
        better = {"workbench": 0, "prompt_only": 0, "tie": 0}
        deltas = []
        for run_id, prompt_only, workbench in paired:
            before = _number(name, getattr(prompt_only, name))
            after = _number(name, getattr(workbench, name))
            deltas.append(after - before)
            if after == before:
                better["tie"] += 1
            elif (after < before) == (name in FEWER_IS_BETTER):
                better["workbench"] += 1
                gained[run_id] = True
            else:
                better["prompt_only"] += 1
        outcomes[name] = {**better, "median_delta": statistics.median(deltas)}
    return {
        "n": len(paired),
        "unpaired": [run_id for run_id, got in by_run.items() if len(got) < len(PIPELINES)],
        "outcomes": outcomes,
        "no_gain": [run_id for run_id, _, _ in paired if not gained[run_id]],
    }


def _number(name: str, value: object) -> int:
    if name == "files_outside_scope":
        return len(value)
    if name == "handoff_quality":
        return HANDOFF_LEVELS.index(value)
    return int(value)
