"""Parallel subagents whose results stream back to the orchestrator."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Awaitable, Callable

from harness.core import count_tokens
from harness.store import SessionStore, Turn

RunSubagent = Callable[[str, str], Awaitable[str]]


async def fan_out(store: SessionStore, parent: str, tasks: list[str], run: RunSubagent,
                  max_parallel: int = 5) -> AsyncIterator[str]:
    """Run each task as a subagent and stream the outcomes as Server-Sent Events.

    Task i (counting from 0) runs as run(f"{parent}.sub{i + 1:02d}", tasks[i]),
    linked under parent just before it starts. At most max_parallel subagents
    run at once, and the next task starts as soon as any one finishes. Each
    outcome is sent as soon as its subagent finishes, in the order they finish:

        event: subagent_result
        data: {"session_id": "<sub>", "result": "<what run returned>"}

    A subagent that raises is sent as event: error with data
    {"session_id": "<sub>", "error": "<ExceptionType>: <message>"}, and the
    others carry on. Only that text returns to the orchestrator: the result,
    or "error: <ExceptionType>: <message>", is appended to parent's session as
    Turn("subagent", text). After the last subagent:

        event: done
        data: {"results": <ok>, "errors": <failed>, "orchestrator_tokens": <tokens in parent's session>}

    data is one line of JSON, and every event ends with a blank line. If the
    consumer stops reading early, subagents still running are cancelled before
    the stream closes, and no new ones start.
    """
    raise NotImplementedError
    yield
