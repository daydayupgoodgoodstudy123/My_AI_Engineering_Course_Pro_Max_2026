"""Parallel subagents whose results stream back to the orchestrator."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Awaitable, Callable

from harness.core import count_tokens
from harness.store import SessionStore, Turn

RunSubagent = Callable[[str, str], Awaitable[str]]


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


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
    finished: asyncio.Queue = asyncio.Queue()
    running: dict[str, asyncio.Task] = {}
    queue = list(enumerate(tasks))[::-1]

    async def one(session_id: str, prompt: str) -> None:
        try:
            result = await run(session_id, prompt)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await finished.put((session_id, None, f"{type(exc).__name__}: {exc}"))
        else:
            await finished.put((session_id, result, None))

    def start_next() -> None:
        index, prompt = queue.pop()
        session_id = f"{parent}.sub{index + 1:02d}"
        store.link_sub(parent, session_id)
        running[session_id] = asyncio.ensure_future(one(session_id, prompt))

    ok = failed = 0
    try:
        while queue and len(running) < max_parallel:
            start_next()
        while running:
            session_id, result, error = await finished.get()
            del running[session_id]
            if queue:
                start_next()
            if error is None:
                ok += 1
                store.append(parent, Turn("subagent", result))
                yield _event("subagent_result", {"session_id": session_id, "result": result})
            else:
                failed += 1
                store.append(parent, Turn("subagent", f"error: {error}"))
                yield _event("error", {"session_id": session_id, "error": error})
        tokens = sum(count_tokens(turn.content) for turn in store.load(parent))
        yield _event("done", {"results": ok, "errors": failed, "orchestrator_tokens": tokens})
    finally:
        for task in running.values():
            task.cancel()
        await asyncio.gather(*running.values(), return_exceptions=True)
