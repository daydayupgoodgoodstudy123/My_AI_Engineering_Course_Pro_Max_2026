"""Per-session dashboard rows: what Langfuse / Phoenix / Opik show per session."""
from __future__ import annotations

from dataclasses import dataclass

from .judge import categorize_failures, scripted_llm_judge
from .spans import Span, TraceCollector


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    trace_count: int
    span_count: int
    error_count: int
    tokens: int
    eval_score_mean: float
    failure_reasons: dict[str, int]


def summarize_session(session_id: str, spans: list[Span]) -> SessionSummary:
    """One dashboard row for a session's spans.

    trace_count counts distinct traces. The judge scores each trace on that trace's
    spans alone, and eval_score_mean is the mean of those scores over the session's
    traces. tokens adds up the "tokens" attribute of every span.
    """
    traces: dict[str, list[Span]] = {}
    for span in spans:
        traces.setdefault(span.trace_id, []).append(span)
    scores = [scripted_llm_judge(trace)[0] for trace in traces.values()]
    return SessionSummary(
        session_id=session_id,
        trace_count=len(traces),
        span_count=len(spans),
        error_count=sum(1 for s in spans if s.status == "error"),
        tokens=sum(s.attributes.get("tokens", 0) for s in spans),
        eval_score_mean=sum(scores) / len(scores),
        failure_reasons=dict(categorize_failures(spans)),
    )


def summarize(collector: TraceCollector) -> list[SessionSummary]:
    """One row per session, lowest eval_score_mean first, ties by session_id."""
    summaries = [
        summarize_session(session_id, spans)
        for session_id, spans in collector.by_session().items()
    ]
    summaries.sort(key=lambda s: (s.eval_score_mean, s.session_id))
    return summaries
