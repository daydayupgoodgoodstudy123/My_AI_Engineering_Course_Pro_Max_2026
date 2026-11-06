"""The lesson's four deterministic prompt-response rubric components."""
from __future__ import annotations

import json
import re


CRITERIA = ("length_compliant", "keyword_coverage", "no_violations", "format_valid")


def score_response(response_text: str, criteria: dict) -> dict:
    """Score the enabled rubric components and their unweighted mean.

    max_words uses whitespace words. Keyword/forbidden matches are case-
    insensitive substrings, preserve criteria order, and empty required words
    have coverage 1. JSON means any complete value json.loads accepts.
    bullet_points follows the lesson's Python heuristic: at least half of
    nonblank stripped lines begin with '-', '*' or '1' (empty text passes).
    numbered_list needs at least two lines beginning with digits then '.'.
    An unrecognized format name passes, as in the source's fallback branch.
    Composite is rounded to 3 decimals; no enabled components yields 0.0.
    """
    scores = {}
    if "max_words" in criteria:
        scores["word_count"] = len(response_text.split())
        scores["length_compliant"] = scores["word_count"] <= criteria["max_words"]
    lowered = response_text.lower()
    if "required_keywords" in criteria:
        keywords = criteria["required_keywords"]
        found = [word for word in keywords if word.lower() in lowered]
        scores["keywords_found"] = found
        scores["keyword_coverage"] = len(found) / len(keywords) if keywords else 1.0
    if "forbidden_phrases" in criteria:
        violations = [phrase for phrase in criteria["forbidden_phrases"] if phrase.lower() in lowered]
        scores["forbidden_violations"] = violations
        scores["no_violations"] = not violations
    if "expected_format" in criteria:
        fmt = criteria["expected_format"]
        if fmt == "json":
            try:
                json.loads(response_text)
                scores["format_valid"] = True
            except (json.JSONDecodeError, TypeError):
                scores["format_valid"] = False
        elif fmt == "bullet_points":
            lines = [line.strip() for line in response_text.split("\n") if line.strip()]
            scores["format_valid"] = sum(line.startswith(("-", "*", "1")) for line in lines) >= len(lines) * 0.5
        elif fmt == "numbered_list":
            scores["format_valid"] = len(re.findall(r"^\d+\.", response_text, re.MULTILINE)) >= 2
        else:
            scores["format_valid"] = True
    enabled = [float(scores[name]) for name in CRITERIA if name in scores]
    scores["composite_score"] = round(sum(enabled) / len(enabled), 3) if enabled else 0.0
    return scores


def compare_models(test_results: dict[str, dict], criteria: dict) -> tuple[dict, list]:
    """Score replay results and rank by descending composite, preserving input ties.

    Each result has response, tokens, api_latency_ms. Return (comparison,
    ranked pairs); the metadata is retained and no input object is mutated.
    """
    comparison = {
        model: {"scores": score_response(result["response"], criteria),
                "tokens": result["tokens"], "latency_ms": result["api_latency_ms"]}
        for model, result in test_results.items()
    }
    ranked = sorted(comparison.items(), key=lambda pair: pair[1]["scores"]["composite_score"], reverse=True)
    return comparison, ranked
