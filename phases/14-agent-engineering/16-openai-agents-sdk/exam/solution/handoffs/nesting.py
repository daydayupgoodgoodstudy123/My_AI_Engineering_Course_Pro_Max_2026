"""nest_handoff_history: collapse the earlier conversation into one summary before a handoff."""
from __future__ import annotations

import json

from .items import AssistantMessage, HandoffItem, HistorySummary, Item, ToolItem, UserMessage


def summary_line(item: Item) -> str:
    """How one earlier item reads inside a HistorySummary:

        UserMessage       user: <text>
        AssistantMessage  <agent>: <text>
        ToolItem          <agent> called <tool> <args as JSON> -> <output>
        HandoffItem       <source> handed off to <target>

    For example: triage called order_status {"order": 9001} -> shipped 2026-10-29
    """
    if isinstance(item, UserMessage):
        return f"user: {item.text}"
    if isinstance(item, AssistantMessage):
        return f"{item.agent}: {item.text}"
    if isinstance(item, ToolItem):
        return f"{item.agent} called {item.tool} {json.dumps(item.args, ensure_ascii=False)} -> {item.output}"
    if isinstance(item, HandoffItem):
        return f"{item.source} handed off to {item.target}"
    raise TypeError(f"no summary line for {item!r}")


def nest_handoff_history(conversation: list[Item]) -> list[Item]:
    """The conversation the next agent reads after a nested handoff.

    Every item before the latest user message is collapsed into one HistorySummary, one line per
    item, oldest first. A HistorySummary among those items adds its own lines as they are, so a
    summary is never summarized again. The latest user message and everything after it stay as they
    are. When nothing comes before the latest user message, there is no summary. The list passed in
    is not changed.
    """
    starts = [i for i, item in enumerate(conversation) if isinstance(item, UserMessage)]
    if not starts:
        raise ValueError("a conversation to nest needs a user message")
    latest = starts[-1]
    lines: list[str] = []
    for item in conversation[:latest]:
        if isinstance(item, HistorySummary):
            lines.extend(item.lines)
        else:
            lines.append(summary_line(item))
    summary = [HistorySummary(tuple(lines))] if lines else []
    return summary + list(conversation[latest:])
