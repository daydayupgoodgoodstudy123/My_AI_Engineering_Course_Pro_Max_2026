"""Evaluate an agent on many tasks at once and report each task the moment it is graded."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from .harness import Patch, Task


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
    raise NotImplementedError
