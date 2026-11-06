"""A learning curve over many tasks: every task's trials, reported as CSV while they run."""
from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

from .judge import Trial, Verdict, judge, worth_reflecting
from .memory import DEFAULT_TTL, EpisodicMemory, Reflection

FIELDS = ("task", "trial", "success", "evaluator", "cumulative_success_rate")


async def learning_curve(
    tasks: Sequence[str],
    attempt: Callable[[str, int, list[Reflection]], Awaitable[Trial]],
    reflect: Callable[[Trial, Verdict], str],
    task_class: str,
    max_trials: int = 3,
    ttl: int = DEFAULT_TTL,
) -> AsyncIterator[str]:
    """Run every task at once, up to max_trials trials each, and stream the learning curve as CSV.

    Each task has its own episodic memory. A task's trials run one after another, as in
    run_trials: trial n awaits attempt(task, n, memory.visible(n)), is judged, and a failure worth
    reflecting on stores Reflection(n, task_class, reflect(trial, verdict), ttl) in that task's
    memory; a success ends the task. Different tasks run concurrently.

    The first string is the header row: task,trial,success,evaluator,cumulative_success_rate.
    Then every trial gets one row as soon as it finishes, in the order trials finish: success is
    1 or 0, evaluator is the verdict's source, and cumulative_success_rate is the share of all
    the tasks solved so far, with four decimals. Each string is one CSV record, as csv.writer
    writes it. Task names must be unique (ValueError).
    """
    names = list(tasks)
    if len(set(names)) != len(names):
        raise ValueError("task names must be unique")
    yield _record(FIELDS)
    queue: asyncio.Queue = asyncio.Queue()

    async def run(task: str) -> None:
        memory = EpisodicMemory()
        try:
            for n in range(1, max_trials + 1):
                trial = await attempt(task, n, memory.visible(n))
                verdict = judge(trial)
                if worth_reflecting(verdict):
                    memory.add(Reflection(n, task_class, reflect(trial, verdict), ttl))
                queue.put_nowait((task, n, verdict))
                if verdict.success:
                    break
        except Exception as error:  # hand it to the reader, which raises it
            queue.put_nowait(error)
        else:
            queue.put_nowait(None)

    runners = [asyncio.create_task(run(task)) for task in names]
    solved = finished = 0
    try:
        while finished < len(runners):
            item = await queue.get()
            if item is None:
                finished += 1
                continue
            if isinstance(item, Exception):
                raise item
            task, n, verdict = item
            solved += verdict.success
            rate = f"{solved / len(names):.4f}"
            yield _record((task, n, 1 if verdict.success else 0, verdict.source, rate))
    finally:
        for runner in runners:
            runner.cancel()


def _record(values) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(values)
    return out.getvalue()
