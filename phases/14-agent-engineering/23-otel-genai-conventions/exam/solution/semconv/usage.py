"""Token usage per agent run, through agents that call agents."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .tracer import Span

OP = "gen_ai.operation.name"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens)


@dataclass(frozen=True)
class AgentUsage:
    span_id: int
    agent: str | None
    depth: int
    own: Usage
    total: Usage


def agent_usage(spans: Iterable[Span]) -> tuple[list[AgentUsage], Usage]:
    """Roll chat token usage up the tree of agent runs.

    Every invoke_agent span is one agent run, even when two runs share a gen_ai.agent.name.
    A chat span's gen_ai.usage.input_tokens and gen_ai.usage.output_tokens (missing counts
    as 0) belong to its nearest invoke_agent ancestor, through any tool_call spans between
    them. A chat span with no invoke_agent ancestor among the spans is unattributed.

    An agent run's parent run is its nearest invoke_agent ancestor; runs without one are
    roots. depth counts agent runs above it (0 for a root). own is the usage of its own chat
    spans; total adds the totals of its child runs.

    Returns (runs in pre-order, roots and siblings by start_ns then span_id; unattributed usage).
    """
    spans = list(spans)
    by_id = {s.span_id: s for s in spans}
    agents = [s for s in spans if s.attributes.get(OP) == "invoke_agent"]
    own = {a.span_id: Usage() for a in agents}
    children: dict[int | None, list[Span]] = {}
    for a in agents:
        parent = _nearest_agent(a, by_id)
        children.setdefault(parent.span_id if parent else None, []).append(a)

    unattributed = Usage()
    for s in spans:
        if s.attributes.get(OP) != "chat":
            continue
        tokens = Usage(
            int(s.attributes.get("gen_ai.usage.input_tokens", 0)),
            int(s.attributes.get("gen_ai.usage.output_tokens", 0)),
        )
        agent = _nearest_agent(s, by_id)
        if agent is None:
            unattributed += tokens
        else:
            own[agent.span_id] += tokens

    def ordered(key: int | None) -> list[Span]:
        return sorted(children.get(key, []), key=lambda s: (s.start_ns, s.span_id))

    totals: dict[int, Usage] = {}
    order: list[tuple[Span, int]] = []
    stack = [(a, 0) for a in reversed(ordered(None))]
    while stack:
        agent, depth = stack.pop()
        order.append((agent, depth))
        stack.extend((c, depth + 1) for c in reversed(ordered(agent.span_id)))
    for agent, _ in reversed(order):
        totals[agent.span_id] = sum(
            (totals[c.span_id] for c in children.get(agent.span_id, [])), own[agent.span_id]
        )
    result = [
        AgentUsage(a.span_id, a.attributes.get("gen_ai.agent.name"), d, own[a.span_id], totals[a.span_id])
        for a, d in order
    ]
    return result, unattributed


def _nearest_agent(span: Span, by_id: dict[int, Span]) -> Span | None:
    seen = {span.span_id}
    while span.parent_span_id in by_id and span.parent_span_id not in seen:
        span = by_id[span.parent_span_id]
        if span.attributes.get(OP) == "invoke_agent":
            return span
        seen.add(span.span_id)
    return None
