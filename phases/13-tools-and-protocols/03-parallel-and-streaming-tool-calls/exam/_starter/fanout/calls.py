"""Tool calls, and the messages that answer them."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """One call the model asked for: its id, the tool's name and the parsed arguments."""

    id: str
    name: str
    arguments: dict = field(default_factory=dict)


def describe(error: BaseException) -> str:
    """How a failure is reported back to the model: "<ExceptionType>: <message>"."""
    return f"{type(error).__name__}: {error}"


def tool_message(call_id: str, result: Any = None, error: BaseException | None = None) -> dict:
    """The message that answers one call: {"role": "tool", "tool_call_id": ..., "content": ...}.

    content is JSON text: the executor's result, or {"error": describe(error)} when it raised.
    """
    body = result if error is None else {"error": describe(error)}
    return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(body)}
