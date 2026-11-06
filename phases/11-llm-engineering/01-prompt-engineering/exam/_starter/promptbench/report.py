"""Pattern/model scorecards from the lesson's nested comparison reports."""
from __future__ import annotations

from .scoring import CRITERIA


def pattern_scorecard(reports: list[dict]) -> dict:
    """Group case reports by pattern, then model, preserving encounter order.

    Each report has case_id, pattern, comparison (compare_models' first
    result). Each model has case_ids, tokens, mean_latency_ms,
    mean_composite, criteria {name: {count, mean}}, and weakest_criterion.
    A criterion absent everywhere has count 0 and mean None, and cannot be
    weakest. A present zero participates. Ties use CRITERIA order. Duplicate
    (pattern, model, case_id) entries raise ValueError. Empty input yields {}.
    This is report aggregation, not a recursive prompt-execution engine.
    """
    raise NotImplementedError
