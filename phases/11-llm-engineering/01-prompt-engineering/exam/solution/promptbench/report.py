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
    grouped = {}
    seen = set()
    for report in reports:
        pattern = report["pattern"]
        for model, result in report["comparison"].items():
            key = (pattern, model, report["case_id"])
            if key in seen:
                raise ValueError("duplicate pattern/model/case")
            seen.add(key)
            rows = grouped.setdefault(pattern, {}).setdefault(model, [])
            rows.append((report["case_id"], result))
    output = {}
    for pattern, models in grouped.items():
        output[pattern] = {}
        for model, rows in models.items():
            components = {}
            for name in CRITERIA:
                values = [float(result["scores"][name]) for _, result in rows if name in result["scores"]]
                components[name] = {"count": len(values), "mean": round(sum(values) / len(values), 3) if values else None}
            available = [name for name in CRITERIA if components[name]["count"]]
            weakest = min(available, key=lambda name: components[name]["mean"]) if available else None
            output[pattern][model] = {
                "case_ids": [case for case, _ in rows],
                "tokens": sum(result["tokens"] for _, result in rows),
                "mean_latency_ms": round(sum(result["latency_ms"] for _, result in rows) / len(rows), 3),
                "mean_composite": round(sum(result["scores"]["composite_score"] for _, result in rows) / len(rows), 3),
                "criteria": components,
                "weakest_criterion": weakest,
            }
    return output
