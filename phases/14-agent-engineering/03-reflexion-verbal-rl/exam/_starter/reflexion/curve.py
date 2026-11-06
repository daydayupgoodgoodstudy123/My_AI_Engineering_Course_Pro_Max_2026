"""A learning curve over many tasks: every task's trials, reported as CSV while they run."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

from .judge import Trial, Verdict
from .memory import DEFAULT_TTL, Reflection

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
    raise NotImplementedError
