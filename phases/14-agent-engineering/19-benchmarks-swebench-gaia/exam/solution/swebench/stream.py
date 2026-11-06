"""Evaluate an agent on many tasks at once and report each task the moment it is graded."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from .harness import STATUSES, Patch, Task, run_task


@dataclass(frozen=True)
class AgentRun:
    """What the agent hands back for one task: its patch and what producing it cost."""

    patch: Patch
    tokens: int
    steps: int


Agent = Callable[[Task], Awaitable[AgentRun]]


async def evaluate_stream(tasks: list[Task], agent: Agent, concurrency: int = 4) -> AsyncIterator[str]:
    """Run the agent on every task, at most `concurrency` tasks at a time, and grade each patch
    with run_task. Tasks start in list order as slots free up.

    Yields one JSON line per task as soon as that task is graded (completion order), with the keys
    in this order, as json.dumps writes them by default:
    {"instance_id", "status", "fail_to_pass": [passed, total], "pass_to_pass": [passed, total],
     "tokens", "steps", "error"}, where error is null. When the agent raises, the task's status
    is "error", its pass counts are 0, tokens and steps are null, and error is
    "<exception type>: <message>"; the other tasks carry on.
    After every task, a last line {"summary": {"resolved": n, "unresolved": n, "invalid": n,
    "error": n}} with all four counts. Every line ends with "\\n".
    Closing the stream early cancels the agents still running and waits for them to stop.
    concurrency below 1 raises ValueError.
    """
    if concurrency < 1:
        raise ValueError(f"concurrency must be at least 1, got {concurrency}")
    slots = asyncio.Semaphore(concurrency)
    done: asyncio.Queue = asyncio.Queue()

    async def work(task: Task) -> None:
        async with slots:
            try:
                run = await agent(task)
            except Exception as exc:
                await done.put(_line(task, "error", 0, 0, None, None, f"{type(exc).__name__}: {exc}"))
                return
            result = run_task(task, run.patch)
            await done.put(
                _line(task, result.status, result.ftp_passed, result.ptp_passed, run.tokens, run.steps, None)
            )

    workers = [asyncio.create_task(work(task)) for task in tasks]
    counts = dict.fromkeys(STATUSES, 0)
    try:
        for _ in tasks:
            status, line = await done.get()
            counts[status] += 1
            yield line
        yield json.dumps({"summary": counts}) + "\n"
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


def _line(task: Task, status: str, ftp: int, ptp: int, tokens, steps, error) -> tuple[str, str]:
    event = {
        "instance_id": task.instance_id,
        "status": status,
        "fail_to_pass": [ftp, len(task.fail_to_pass)],
        "pass_to_pass": [ptp, len(task.pass_to_pass)],
        "tokens": tokens,
        "steps": steps,
        "error": error,
    }
    return status, json.dumps(event) + "\n"
