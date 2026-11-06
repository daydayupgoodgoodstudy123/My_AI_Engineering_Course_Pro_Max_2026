"""Planning how to batch tasks into subagents.

A subagent keeps what it reads in its own context and hands back only a
summary, so the orchestrator's context stays small, but every subagent costs a
fixed overhead on top. compare_plans works out every way to batch the tasks,
and choose_plan picks the one to run.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Costs:
    """What a plan costs, in tokens as count_tokens counts them.

    prompt is the orchestrator's context before any task: its prompt.
    brief is the prompt the orchestrator hands each subagent.
    overhead is the fixed cost of each subagent: its system prompt and tool
    definitions. A subagent hands back one summary of its whole batch, of
    summary_base + summary_per_task * (tasks in the batch) tokens.
    """

    prompt: int
    brief: int
    overhead: int
    summary_base: int
    summary_per_task: int


@dataclass(frozen=True)
class Plan:
    """One way to run the tasks.

    batch_size 0 means no subagents: the orchestrator runs every task itself,
    and batches and subagent_tokens are empty. Otherwise batches holds each
    subagent's task names, and subagent_tokens the size of each subagent's
    context, in the same order.
    """

    batch_size: int
    batches: tuple[tuple[str, ...], ...]
    orchestrator_tokens: int
    subagent_tokens: tuple[int, ...]
    total_tokens: int

    @property
    def subagents(self) -> int:
        return len(self.batches)


def compare_plans(tasks: list[tuple[str, int]], costs: Costs) -> list[Plan]:
    """Every way to run tasks, given as (name, tokens the task reads) pairs.

    The first plan has no subagents: the orchestrator runs every task itself,
    so every read lands in its own context. Then comes one plan for each batch
    size k from 1 to len(tasks): the tasks are cut, in order, into batches of
    k, the last batch taking whatever is left, and each batch runs in a
    subagent of its own.

    A subagent's context holds the overhead, the brief, the reads of its batch
    and the summary it writes. Only the summaries return to the orchestrator,
    whose context is the prompt plus one summary per subagent. total_tokens
    adds up every context in the plan: the orchestrator's and every subagent's.
    """
    alone = costs.prompt + sum(read for _, read in tasks)
    plans = [Plan(0, (), alone, (), alone)]
    for k in range(1, len(tasks) + 1):
        batches = [tasks[i:i + k] for i in range(0, len(tasks), k)]
        summaries = [costs.summary_base + costs.summary_per_task * len(batch) for batch in batches]
        orchestrator = costs.prompt + sum(summaries)
        contexts = tuple(
            costs.overhead + costs.brief + sum(read for _, read in batch) + summary
            for batch, summary in zip(batches, summaries)
        )
        names = tuple(tuple(name for name, _ in batch) for batch in batches)
        plans.append(Plan(k, names, orchestrator, contexts, orchestrator + sum(contexts)))
    return plans


def choose_plan(tasks: list[tuple[str, int]], costs: Costs, cap: int, window: int) -> Plan:
    """The plan to run: the cheapest one that fits.

    A plan fits when the orchestrator's context is at most cap and every
    subagent's context is at most window, the size of a subagent's own context
    window. Of the plans that fit, the one with the lowest total_tokens; ties go
    to fewer subagents, then to the smaller batch size. ValueError if no plan
    fits.
    """
    fits = [
        plan for plan in compare_plans(tasks, costs)
        if plan.orchestrator_tokens <= cap and all(tokens <= window for tokens in plan.subagent_tokens)
    ]
    if not fits:
        raise ValueError(f"no plan fits an orchestrator cap of {cap} and a subagent window of {window}")
    return min(fits, key=lambda plan: (plan.total_tokens, plan.subagents, plan.batch_size))
