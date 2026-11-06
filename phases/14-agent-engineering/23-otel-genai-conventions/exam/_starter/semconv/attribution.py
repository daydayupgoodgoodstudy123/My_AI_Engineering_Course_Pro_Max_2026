"""Which tool errors go with which models, from GenAI span attributes alone."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .tracer import Span

OP = "gen_ai.operation.name"


@dataclass(frozen=True)
class ToolErrorRow:
    provider: str
    model: str
    tool: str
    calls: int
    errors: int


@dataclass(frozen=True)
class ToolErrorReport:
    rows: list[ToolErrorRow]
    orphaned: int


def tool_errors(spans: Iterable[Span]) -> ToolErrorReport:
    """Count tool calls and tool errors per (provider, model, tool).

    A tool span has gen_ai.operation.name "tool_call"; it failed if it has error.type. Each
    tool span is charged to the chat span that requested it:
      - if the tool span's parent is a chat span, that chat span;
      - if its parent is an invoke_agent span, the chat span under that same invoke_agent
        span that started last at or before the tool span started (ties: the smaller span_id).
    A tool span with no parent, a parent that is not among the spans, another kind of parent,
    or no such chat span is orphaned: it is counted in orphaned and in no row.

    model is the chat span's gen_ai.response.model (the model that actually answered), else
    its gen_ai.request.model. provider is the chat span's gen_ai.provider.name, else that of
    the nearest invoke_agent span above it, else "unknown". Rows are sorted by
    (provider, model, tool).
    """
    raise NotImplementedError
