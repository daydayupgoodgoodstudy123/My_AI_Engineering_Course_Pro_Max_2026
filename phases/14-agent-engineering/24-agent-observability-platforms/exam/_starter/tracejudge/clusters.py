"""Trace clustering: group traces by the shape of their span tree, flag rare shapes."""
from __future__ import annotations

from dataclasses import dataclass

from .spans import Span


@dataclass(frozen=True)
class Cluster:
    signature: str
    trace_ids: list[str]
    anomalous: bool


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
    raise NotImplementedError


def cluster_traces(spans: list[Span], min_share: float) -> list[Cluster]:
    """Group traces by signature and flag the rare ones.

    spans may hold many traces; span ids are only unique within a trace. A cluster
    is anomalous when its share of all traces is below min_share (a share of exactly
    min_share is not). Clusters come largest first, ties by signature; trace_ids are
    in the order each trace's first span appears in spans.
    """
    raise NotImplementedError
