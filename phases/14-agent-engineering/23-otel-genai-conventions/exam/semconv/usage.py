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
    raise NotImplementedError
