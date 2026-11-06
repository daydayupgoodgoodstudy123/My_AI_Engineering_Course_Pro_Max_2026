"""Stream a run to a UI as server-sent events, with the reasoning on its own channel."""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from .loop import FINISH, AgentLoop, finish_answer
from .messages import Message

_LINE_BREAK = re.compile(r"\r\n|\r|\n")


async def stream_run(loop: AgentLoop, task: str) -> AsyncIterator[str]:
    """Run a task like AgentLoop.run, but through the model's stream(), and yield what happens as
    server-sent events, each one as soon as it happens:

        reasoning    a piece of the model's thinking, as it arrives
        action       a tool call, as JSON: {"name": ..., "args": ...}
        observation  the observation string for that call's result
        final        the answer, once, when the loop stops (empty when max_turns ran out)

    Each item yielded is one event: an "event: <type>" line, a "data: " line for each line of its
    text, and a blank line. Thinking is sent only as reasoning events, and assistant text that comes
    with tool calls is not an answer, so it is not sent at all. The history grows exactly as it
    does in AgentLoop.run.
    """
    loop.history.append(Message("user", task))
    for _ in range(loop.max_turns):
        reply = None
        async for kind, value in loop.model.stream(loop.messages()):
            if kind == "thinking":
                yield _event("reasoning", value)
            else:
                reply = value
        message = loop.record(reply)
        if not message.tool_calls:
            yield _event("final", message.content)
            return
        for call in message.tool_calls:
            if call.name == FINISH:
                yield _event("final", finish_answer(call))
                return
            yield _event("action", json.dumps({"name": call.name, "args": call.args}))
            yield _event("observation", loop.act(call).content)
    yield _event("final", "")


def _event(kind: str, text: str) -> str:
    data = "".join(f"data: {line}\n" for line in _LINE_BREAK.split(text))
    return f"event: {kind}\n{data}\n"
