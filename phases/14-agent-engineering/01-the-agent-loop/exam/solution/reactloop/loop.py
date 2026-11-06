"""The agent loop: observe, think, act, until a stop condition fires."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .messages import Message, ToolCall
from .tools import ToolRegistry

FINISH = "finish"


@dataclass
class Outcome:
    answer: str
    stop: str  # "finish", "no_tool_calls" or "max_turns"
    history: list[Message]


def to_observation(result: Any) -> str:
    """The observation string for a tool result: a string as it is, anything else as JSON."""
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


def finish_answer(call: ToolCall) -> str:
    """The answer a finish call gives: its "answer" argument, or its only positional one."""
    if isinstance(call.args, dict):
        return str(call.args.get("answer", ""))
    return str(call.args[0]) if call.args else ""


class AgentLoop:
    """The ReAct loop over a native-reasoning model.

    The model reads the message buffer and replies with a dict: "text", "tool_calls" (a list of
    {"name", "args"}), "thinking" (readable reasoning) and "reasoning" (an opaque reasoning item),
    each of them optional. The loop stops when the model calls the finish tool (its answer argument
    is the answer), when an assistant turn contains no tool calls (its text is the answer), or after
    max_turns model turns.
    """

    def __init__(
        self,
        model: Any,
        tools: ToolRegistry,
        *,
        max_turns: int = 12,
        observe: Callable[[Any], str] = to_observation,
        history: list[Message] | None = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.max_turns = max_turns
        self.observe = observe
        self.history: list[Message] = list(history or [])

    def run(self, task: str) -> Outcome:
        """Run one task to a stop condition, continuing the conversation already in the history."""
        self.history.append(Message("user", task))
        for _ in range(self.max_turns):
            message = self.record(self.model.respond(self.messages()))
            if not message.tool_calls:
                return Outcome(message.content, "no_tool_calls", self.history)
            for call in message.tool_calls:
                if call.name == FINISH:
                    return Outcome(finish_answer(call), "finish", self.history)
                self.act(call)
        return Outcome("", "max_turns", self.history)

    def messages(self) -> list[Message]:
        """What the model reads: the history so far, every tool result as its observation string."""
        return list(self.history)

    def record(self, reply: dict[str, Any]) -> Message:
        """Append the assistant turn for a reply to the history, and return it."""
        message = Message(
            "assistant",
            content=reply.get("text", ""),
            tool_calls=[ToolCall(c["name"], c.get("args", {})) for c in reply.get("tool_calls", [])],
            reasoning=reply.get("reasoning"),
            thinking=reply.get("thinking", ""),
        )
        self.history.append(message)
        return message

    def act(self, call: ToolCall) -> Message:
        """Run one tool call and append its result to the history as a tool turn, and return it."""
        result = self.tools.dispatch(call)
        message = Message("tool", self.observe(result), name=call.name, result=result)
        self.history.append(message)
        return message
