"""The message buffer the loop and the model share."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """One tool the model asked for: keyword arguments as a dict, or positional ones as a list."""

    name: str
    args: dict[str, Any] | list[Any] = field(default_factory=dict)


@dataclass
class Message:
    """One entry of the message buffer.

    user:      content is what the user asked.
    assistant: content is the visible text, tool_calls are the calls the model asked for, thinking is
               the readable reasoning the provider sent, and reasoning is the opaque reasoning item it
               returned with the turn (None when it returned none).
    tool:      name is the tool that ran, result is what it returned, and content is that result as the
               observation string the model reads.
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning: bytes | None = None
    thinking: str = ""
    name: str = ""
    result: Any = None
