"""Trigger metrics for one skill: confusion counts, ratios and per-case repeated-run results."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .cases import NEGATIVE_CATEGORIES, TriggerCase, check_cases, check_predictions


def classification_metrics(expected: Sequence[bool], predicted: Sequence[bool]) -> dict[str, float | int]:
    """Raw confusion counts, with precision, recall, F1 and accuracy rounded to 4 places.

    A ratio whose denominator is zero is 0.0. F1 is the harmonic mean of precision and recall,
    and 0.0 when both are 0. The rounded ratios are for people reading the report; a gate
    compares its thresholds with the raw counts.
    """
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted lengths must match")
    tp = sum(want and got for want, got in zip(expected, predicted))
    fp = sum(not want and got for want, got in zip(expected, predicted))
    tn = sum(not want and not got for want, got in zip(expected, predicted))
    fn = sum(want and not got for want, got in zip(expected, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round((tp + tn) / len(expected), 4) if expected else 0.0,
    }


def run_matched(case: TriggerCase, predicted: str | None, skill: str) -> bool:
    """A run matches when it invoked skill exactly when the case wants skill."""
    return (predicted == skill) == (case.expected_skill == skill)


def trigger_report(
    cases: Sequence[TriggerCase],
    predictions: Mapping[str, Sequence[str | None]],
    skill: str,
) -> dict[str, object]:
    """Score skill's trigger boundary over repeated runs of labeled cases.

    predictions maps every case id to the skill the router invoked on each run, None where it
    abstained. The metrics pool every run of every case. A case passes only when every one of
    its runs matched. false_positives counts, for each negative category, the runs that invoked
    skill on a case of that category.
    """
    check_cases(cases, skill)
    check_predictions(cases, predictions)
    expected: list[bool] = []
    invoked: list[bool] = []
    false_positives = dict.fromkeys(NEGATIVE_CATEGORIES, 0)
    results = []
    for case in cases:
        runs = list(predictions[case.case_id])
        wants = case.expected_skill == skill
        fired = [prediction == skill for prediction in runs]
        matched = [run_matched(case, prediction, skill) for prediction in runs]
        expected += [wants] * len(runs)
        invoked += fired
        if not wants:
            false_positives[case.category] += sum(fired)
        results.append(
            {
                "id": case.case_id,
                "category": case.category,
                "predictions": runs,
                "matched": sum(matched),
                "runs": len(runs),
                "passed": all(matched),
            }
        )
    return {
        "skill": skill,
        "metrics": classification_metrics(expected, invoked),
        "false_positives": false_positives,
        "cases": results,
    }
