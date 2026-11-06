"""The scripted LLM judge and failure categories, as in the lesson's code/main.py."""
from __future__ import annotations

from collections import Counter

from .spans import Span


def scripted_llm_judge(trace_spans: list[Span]) -> tuple[float, str]:
    """Score one trace against the rubric and return (score, verdict).

    Start at 1.0; an error span costs 0.4, no span with a
    gen_ai.output.reference_id costs 0.3, no tool_call span costs 0.1, and a span
    over 2000 tokens costs 0.1. The score never goes below 0.0.
    Verdict: PASS at 0.8 or more, WARN at 0.5 or more, otherwise FAIL.
    """
    errors = sum(1 for s in trace_spans if s.status == "error")
    has_tool = any(s.name.startswith("tool_call") for s in trace_spans)
    has_final = any(s.attributes.get("gen_ai.output.reference_id") for s in trace_spans)
    tokens_over = any(s.attributes.get("tokens", 0) > 2000 for s in trace_spans)
    score = 1.0
    if errors:
        score -= 0.4
    if not has_final:
        score -= 0.3
    if not has_tool:
        score -= 0.1
    if tokens_over:
        score -= 0.1
    score = max(0.0, score)
    if score >= 0.8:
        verdict = "PASS"
    elif score >= 0.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"
    return score, verdict


def categorize_failures(spans: list[Span]) -> Counter:
    """Count the error.reason of every error span ("unknown" when it has none)."""
    reasons: Counter = Counter()
    for span in spans:
        if span.status != "error":
            continue
        reasons[span.attributes.get("error.reason", "unknown")] += 1
    return reasons
