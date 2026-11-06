"""Cascade radius: how far each root-cause failure spread through a trace."""
from __future__ import annotations

from dataclasses import dataclass

from .trace import Trace, references


@dataclass(frozen=True)
class Cascade:
    step: int  # index of the root-cause failure
    radius: int  # steps it affected downstream
    depth: int  # hops along the longest chain of affected steps
    systems: list[str]  # systems those affected tool calls touched, sorted


def system_of(tool: str) -> str:
    """The system a tool belongs to: the part of its name before the first dot."""
    return tool.split(".", 1)[0]


def cascade_report(trace: Trace) -> list[Cascade]:
    """One Cascade per root-cause failure in the trace, in step order.

    Steps form a data-dependency DAG: step j depends on step i when references() of step j
    names i. A failure is a tool call with status "error". A step is affected by a failure
    when it depends on it directly or through other steps. A root cause is a failure that
    no other failure affects; failures that a root affects count in its radius, and a step
    affected by two roots counts for both.

    radius counts each affected step once, messages included. depth is the number of hops
    on the longest dependency chain from the root to an affected step. systems lists the
    system_of() of the affected tool calls, each once. A step that references itself, a
    later step or a step that does not exist makes the trace malformed: ValueError.
    """
    steps = trace.steps
    children: list[list[int]] = [[] for _ in steps]
    for j, step in enumerate(steps):
        for i in sorted(references(step)):
            if not 0 <= i < j:
                raise ValueError(f"step {j} references step {i}, which has not run before it")
            children[i].append(j)

    failed = [i for i, s in enumerate(steps) if s.kind == "tool_call" and s.status == "error"]
    affected: dict[int, set[int]] = {}
    for root in failed:
        seen: set[int] = set()
        stack = list(children[root])
        while stack:
            j = stack.pop()
            if j not in seen:
                seen.add(j)
                stack.extend(children[j])
        affected[root] = seen

    caused = set().union(*affected.values()) if affected else set()
    report = []
    for root in failed:
        if root in caused:
            continue
        reach = affected[root]
        depth = {root: 0}
        for j in sorted(reach):  # indices are a topological order
            depth[j] = 1 + max(depth[i] for i in references(steps[j]) if i in depth)
        systems = sorted({system_of(steps[j].name) for j in reach if steps[j].kind == "tool_call"})
        report.append(Cascade(root, len(reach), max(depth.values()), systems))
    return report
