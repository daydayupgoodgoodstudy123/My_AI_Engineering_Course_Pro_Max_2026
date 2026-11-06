"""Trace clustering: group traces by the shape of their span tree, flag rare shapes."""
from __future__ import annotations

from dataclasses import dataclass

from .spans import Span


@dataclass(frozen=True)
class Cluster:
    signature: str
    trace_ids: list[str]
    anomalous: bool


def _escape(name: str) -> str:
    out = []
    for ch in name:
        if ch in "\\(),":
            out.append("\\")
        out.append(ch)
    return "".join(out)


def signature(trace_spans: list[Span]) -> str:
    """The structural signature of one trace's span tree.

    A span is written as its name, followed by its children in parentheses,
    comma-separated: invoke_agent(chat,tool_call search_tool,chat). A leaf has no
    parentheses. Children are ordered by start_ns, ties by span_id. Inside a name,
    a backslash, "(", ")" and "," are each written with a backslash before them, so
    two different trees never share a signature.

    The trace's signature is its roots' signatures, ordered the same way and joined
    by ",". A root is a span with no parent_id, or whose parent is not in this trace.
    A span that never reaches a root (it sits on a parent cycle) raises ValueError.
    """
    by_id = {span.span_id: span for span in trace_spans}
    children: dict[str, list[Span]] = {}
    roots: list[Span] = []
    for span in by_id.values():
        if span.parent_id is not None and span.parent_id in by_id:
            children.setdefault(span.parent_id, []).append(span)
        else:
            roots.append(span)

    def order(span: Span) -> tuple[int, str]:
        return (span.start_ns, span.span_id)

    reached: set[str] = set()

    def render(span: Span) -> str:
        reached.add(span.span_id)
        kids = sorted(children.get(span.span_id, []), key=order)
        inner = ",".join(render(kid) for kid in kids)
        return _escape(span.name) + (f"({inner})" if kids else "")

    text = ",".join(render(root) for root in sorted(roots, key=order))
    stuck = sorted(set(by_id) - reached)
    if stuck:
        raise ValueError(f"spans on a parent cycle: {stuck}")
    return text


def cluster_traces(spans: list[Span], min_share: float) -> list[Cluster]:
    """Group traces by signature and flag the rare ones.

    spans may hold many traces; span ids are only unique within a trace. A cluster
    is anomalous when its share of all traces is below min_share (a share of exactly
    min_share is not). Clusters come largest first, ties by signature; trace_ids are
    in the order each trace's first span appears in spans.
    """
    traces: dict[str, list[Span]] = {}
    for span in spans:
        traces.setdefault(span.trace_id, []).append(span)
    groups: dict[str, list[str]] = {}
    for trace_id, trace_spans in traces.items():
        groups.setdefault(signature(trace_spans), []).append(trace_id)
    total = len(traces)
    clusters = [
        Cluster(sig, ids, len(ids) / total < min_share) for sig, ids in groups.items()
    ]
    clusters.sort(key=lambda c: (-len(c.trace_ids), c.signature))
    return clusters
