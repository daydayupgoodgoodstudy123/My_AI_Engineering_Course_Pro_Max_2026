"""Conversation items: what an agent's model reads and what a session stores."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    """An answer, and the agent that gave it."""

    agent: str
    text: str


@dataclass(frozen=True)
class ToolItem:
    """One function tool call: who called it, with which arguments, and the text the model got back."""

    agent: str
    tool: str
    args: dict[str, Any]
    output: str


@dataclass(frozen=True)
class HandoffItem:
    """source handed the conversation to target."""

    source: str
    target: str


@dataclass(frozen=True)
class HistorySummary:
    """Earlier conversation collapsed into one item by nest_handoff_history, one line per earlier item."""

    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))


Item = Union[UserMessage, AssistantMessage, ToolItem, HandoffItem, HistorySummary]
