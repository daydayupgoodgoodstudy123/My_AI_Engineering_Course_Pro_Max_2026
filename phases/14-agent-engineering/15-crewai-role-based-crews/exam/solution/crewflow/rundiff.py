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
    found: list[tuple[str, str]] = []

    def walk(good_nodes: Sequence[TraceNode], bad_nodes: Sequence[TraceNode], prefix: str) -> None:
        mine, theirs = _by_occurrence(good_nodes), _by_occurrence(bad_nodes)
        for key, node in mine.items():
            path = prefix + _segment(key)
            other = theirs.get(key)
            if other is None:
                found.append(("missing", path))
                continue
            if node.output != other.output:
                found.append(("changed", path))
            walk(node.children, other.children, path + "/")
        for key in theirs:
            if key not in mine:
                found.append(("extra", prefix + _segment(key)))

    walk(good, bad, "")
    return RunDiff(
        first=found[0][1] if found else None,
        missing=[path for kind, path in found if kind == "missing"],
        extra=[path for kind, path in found if kind == "extra"],
        changed=[path for kind, path in found if kind == "changed"],
    )


def _by_occurrence(nodes: Sequence[TraceNode]) -> dict[tuple[str, int], TraceNode]:
    seen: dict[str, int] = {}
    keyed: dict[tuple[str, int], TraceNode] = {}
    for node in nodes:
        k = seen.get(node.name, 0)
        keyed[(node.name, k)] = node
        seen[node.name] = k + 1
    return keyed


def _segment(key: tuple[str, int]) -> str:
    return f"{key[0]}[{key[1]}]"
