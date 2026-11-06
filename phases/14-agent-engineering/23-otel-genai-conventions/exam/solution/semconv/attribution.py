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
    spans = list(spans)
    by_id = {s.span_id: s for s in spans}
    chats_under: dict[int, list[Span]] = {}
    for s in spans:
        if s.attributes.get(OP) == "chat" and s.parent_span_id is not None:
            chats_under.setdefault(s.parent_span_id, []).append(s)

    counts: dict[tuple[str, str, str], list[int]] = {}
    orphaned = 0
    for tool in spans:
        if tool.attributes.get(OP) != "tool_call":
            continue
        chat = _requesting_chat(tool, by_id, chats_under)
        if chat is None:
            orphaned += 1
            continue
        model = chat.attributes.get("gen_ai.response.model") or chat.attributes.get("gen_ai.request.model")
        key = (_provider(chat, by_id), str(model), str(tool.attributes.get("gen_ai.tool.name")))
        entry = counts.setdefault(key, [0, 0])
        entry[0] += 1
        entry[1] += "error.type" in tool.attributes
    rows = [ToolErrorRow(p, m, t, c, e) for (p, m, t), (c, e) in sorted(counts.items())]
    return ToolErrorReport(rows, orphaned)


def _requesting_chat(tool: Span, by_id: dict[int, Span], chats_under: dict[int, list[Span]]) -> Span | None:
    parent = by_id.get(tool.parent_span_id) if tool.parent_span_id is not None else None
    if parent is None:
        return None
    op = parent.attributes.get(OP)
    if op == "chat":
        return parent
    if op != "invoke_agent":
        return None
    earlier = [c for c in chats_under.get(parent.span_id, []) if c.start_ns <= tool.start_ns]
    if not earlier:
        return None
    return min(earlier, key=lambda c: (-c.start_ns, c.span_id))


def _provider(chat: Span, by_id: dict[int, Span]) -> str:
    if chat.attributes.get("gen_ai.provider.name"):
        return chat.attributes["gen_ai.provider.name"]
    agent = _nearest_agent(chat, by_id)
    if agent is not None and agent.attributes.get("gen_ai.provider.name"):
        return agent.attributes["gen_ai.provider.name"]
    return "unknown"


def _nearest_agent(span: Span, by_id: dict[int, Span]) -> Span | None:
    seen = {span.span_id}
    while span.parent_span_id in by_id and span.parent_span_id not in seen:
        span = by_id[span.parent_span_id]
        if span.attributes.get(OP) == "invoke_agent":
            return span
        seen.add(span.span_id)
    return None
