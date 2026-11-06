"""Orchestrator-workers: an orchestrator LLM decides which workers run, then their outputs are combined.

It looks like an agent loop, but the orchestrator does not loop indefinitely: a run has a round
limit, and each round a limit on how many new subtasks it may start.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Subtask:
    """One piece of work the orchestrator asked for: which worker, and what to tell it."""

    worker: str
    task: str


@dataclass(frozen=True)
class Result:
    subtask: Subtask
    output: str
    round: int  # the round it ran in, counted from 1


@dataclass(frozen=True)
class Orchestrated:
    output: str  # what synthesize returned
    results: list[Result]
    dropped: list[Subtask]
    rounds: int  # how many plans the orchestrator was asked for
    stopped: str  # "done" or "max_rounds"


class PlanError(ValueError):
    """The orchestrator's reply is not a plan this run can carry out."""


Planner = Callable[[str, "list[Result]"], Awaitable[str]]
Worker = Callable[[str], Awaitable[str]]
Synthesizer = Callable[[str, "list[Result]"], Awaitable[str]]


async def orchestrate(
    task: str,
    planner: Planner,
    workers: dict[str, Worker],
    synthesize: Synthesizer,
    max_subtasks: int = 4,
    max_rounds: int = 3,
) -> Orchestrated:
    """Run one task through the orchestrator-workers pattern.

    Each round, planner(task, results) sees the results so far and replies with a JSON plan:

        {"subtasks": [{"worker": "<name>", "task": "<instructions>"}, ...], "done": false}

    A reply of any other shape is a PlanError, and so is a subtask for a worker that is not in
    workers (the error names it). A bad plan raises before any of its subtasks start.

    A subtask is its (worker, task) pair. A repeat within a plan, or a subtask that already ran in
    an earlier round, does not run again. Of the rest, the first max_subtasks start at once; any
    after them are dropped for this round and listed in dropped (a later plan may ask again).

    The run stops after a plan that says "done": true (that plan's subtasks still run) or after
    max_rounds rounds. Then synthesize(task, results) combines every result, in the order the
    orchestrator asked for them, whatever order the workers finished in.
    """
    raise NotImplementedError
