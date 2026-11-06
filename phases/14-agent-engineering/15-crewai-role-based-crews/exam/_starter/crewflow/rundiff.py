"""Diff two runs' trace trees, so that on-call can see where a bad run left a good one."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TraceNode:
    """One node of a run's trace: a Flow step, a Crew kickoff inside a step, a task, and so on down.

    output is what the node produced, or None; children are the nodes it ran, in order.
    """

    name: str
    output: str | None = None
    children: tuple[TraceNode, ...] = ()


@dataclass
class RunDiff:
    first: str | None  # path of the first difference, None when the runs match
    missing: list[str] = field(default_factory=list)  # nodes only the good run has, one path per subtree
    extra: list[str] = field(default_factory=list)  # nodes only the bad run has, one path per subtree
    changed: list[str] = field(default_factory=list)  # nodes in both runs whose outputs differ


def diff_runs(good: Sequence[TraceNode], bad: Sequence[TraceNode]) -> RunDiff:
    """Align two runs' top-level steps, and everything below them, and report the differences.

    Siblings are aligned by name and occurrence: the k-th node called "review" among one run's
    siblings is matched with the k-th node called "review" among the other run's siblings,
    wherever they sit. A node's path is the "name[k]" segments of its ancestors and itself joined
    by "/", k counting from 0 among the siblings of the same name. A node that only one run has is
    reported once, by its own path; nothing below it is listed.

    Every list, and first, follows the order a reader meets the differences going depth first
    through the good run, where a node only the bad run has comes after all of the good run's
    nodes at its level, in the bad run's order. first is the earliest difference of any kind.
    """
    raise NotImplementedError
