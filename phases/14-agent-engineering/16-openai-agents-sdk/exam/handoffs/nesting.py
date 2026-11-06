"""nest_handoff_history: collapse the earlier conversation into one summary before a handoff."""
from __future__ import annotations

from .items import Item


def summary_line(item: Item) -> str:
    """How one earlier item reads inside a HistorySummary:

        UserMessage       user: <text>
        AssistantMessage  <agent>: <text>
        ToolItem          <agent> called <tool> <args as JSON> -> <output>
        HandoffItem       <source> handed off to <target>

    For example: triage called order_status {"order": 9001} -> shipped 2026-10-29
    """
    raise NotImplementedError


def nest_handoff_history(conversation: list[Item]) -> list[Item]:
    """The conversation the next agent reads after a nested handoff.

    Every item before the latest user message is collapsed into one HistorySummary, one line per
    item, oldest first. A HistorySummary among those items adds its own lines as they are, so a
    summary is never summarized again. The latest user message and everything after it stay as they
    are. When nothing comes before the latest user message, there is no summary. The list passed in
    is not changed.
    """
    raise NotImplementedError
