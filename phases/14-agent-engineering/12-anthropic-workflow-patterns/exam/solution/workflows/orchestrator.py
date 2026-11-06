"""Orchestrator-workers: an orchestrator LLM decides which workers run, then their outputs are combined.

It looks like an agent loop, but the orchestrator does not loop indefinitely: a run has a round
limit, and each round a limit on how many new subtasks it may start.
"""
from __future__ import annotations

import asyncio
import json
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
    results: list[Result] = []
    ran: set[Subtask] = set()
    dropped: list[Subtask] = []
    stopped = "max_rounds"
    rounds = 0
    for number in range(1, max_rounds + 1):
        rounds = number
        subtasks, done = _parse_plan(await planner(task, list(results)), workers)
        new = [subtask for subtask in dict.fromkeys(subtasks) if subtask not in ran]
        batch = new[:max_subtasks]
        dropped.extend(new[max_subtasks:])
        outputs = await asyncio.gather(*(workers[s.worker](s.task) for s in batch))
        for subtask, output in zip(batch, outputs):
            ran.add(subtask)
            results.append(Result(subtask, output, number))
        if done:
            stopped = "done"
            break
    output = await synthesize(task, list(results))
    return Orchestrated(output, results, dropped, rounds, stopped)


def _parse_plan(reply: str, workers: dict[str, Worker]) -> tuple[list[Subtask], bool]:
    try:
        plan = json.loads(reply)
    except json.JSONDecodeError as exc:
        raise PlanError(f"the plan is not JSON: {exc}") from None
    if not isinstance(plan, dict):
        raise PlanError("the plan must be a JSON object")
    items, done = plan.get("subtasks"), plan.get("done")
    if not isinstance(items, list) or not isinstance(done, bool):
        raise PlanError('the plan needs a "subtasks" list and a true/false "done"')
    subtasks = []
    for item in items:
        if not (
            isinstance(item, dict) and isinstance(item.get("worker"), str) and isinstance(item.get("task"), str)
        ):
            raise PlanError(f"a subtask needs a worker and a task: {item!r}")
        if item["worker"] not in workers:
            raise PlanError(f"no worker named {item['worker']!r}")
        subtasks.append(Subtask(item["worker"], item["task"]))
    return subtasks, done
