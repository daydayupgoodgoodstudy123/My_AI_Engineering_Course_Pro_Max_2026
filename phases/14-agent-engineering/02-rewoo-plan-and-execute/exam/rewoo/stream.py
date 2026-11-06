"""Run a plan while the planner is still writing it."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .workers import ToolRegistry


async def stream_plan(chunks: AsyncIterator[str], tools: ToolRegistry) -> AsyncIterator[str]:
    """Run each step while the planner is still streaming the plan, and yield one record per step.

    The planner writes one step per line, `#E<k> = <tool>[<input>]`; every other line (its
    reasoning, blank lines) is ignored. A line is complete at its newline, or at the end of the
    stream. The input is everything between the first "[" and the last "]" of the line, and the
    tool gets it, with references filled in, as its only argument.

    A step runs as soon as its line is complete and every step it references has evidence. It may
    refer to a step whose line has not arrived yet, and then waits for it. When several steps are
    ready, the one whose line came first runs first. Each step that finishes yields one record:

        #E<k> = <tool>[<input with references filled in>] -> <evidence>\\n

    A tool that fails gives its error text as the evidence. A step that references a failed or
    skipped step is not run: its record reads `-> skipped` and keeps the input as written. A line
    break inside the input or the evidence is written as one space, so every record is one line.

    A second line for an id that was already written raises ValueError. At the end of the stream,
    a step still waiting for an id the plan never wrote raises KeyError naming it, and steps still
    waiting for each other raise ValueError.
    """
    raise NotImplementedError
