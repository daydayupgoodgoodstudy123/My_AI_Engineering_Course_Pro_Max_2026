"""Stream a run to a UI as server-sent events, with the reasoning on its own channel."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .loop import AgentLoop


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
    raise NotImplementedError
