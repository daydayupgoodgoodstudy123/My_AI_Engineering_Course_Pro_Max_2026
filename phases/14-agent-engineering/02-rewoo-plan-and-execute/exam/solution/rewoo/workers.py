"""Workers: run a plan's steps in dependency order and collect their evidence."""
from __future__ import annotations

import heapq
from collections.abc import Iterable
from typing import Any, Callable

from .plan import MISSING, REF, Evidence, Plan, Step, references


class ToolRegistry:
    """Tools by name. Every tool returns text."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., str]] = {}

    def register(self, name: str, fn: Callable[..., str]) -> None:
        self._tools[name] = fn

    def call(self, name: str, /, *args: Any, **kwargs: Any) -> Evidence:
        """Run one tool. A tool that raises, or a name nobody registered, gives failed evidence."""
        fn = self._tools.get(name)
        if fn is None:
            return Evidence("failed", f"error: unknown tool {name!r}")
        try:
            return Evidence("ok", fn(*args, **kwargs))
        except Exception as exc:
            return Evidence("failed", f"error: {type(exc).__name__}: {exc}")


def resolve_references(value: Any, evidence: dict[str, Evidence]) -> Any:
    """Fill in every #E<k> reference with the text of step E<k>'s evidence.

    References can sit in any string of the arguments, also inside lists and dicts at any depth.
    Other values come back as they are. The plan itself is never modified.
    """
    if isinstance(value, str):
        return REF.sub(lambda m: evidence[f"E{m.group(1)}"].text, value)
    if isinstance(value, list):
        return [resolve_references(item, evidence) for item in value]
    if isinstance(value, dict):
        return {key: resolve_references(item, evidence) for key, item in value.items()}
    return value


def topological(plan: Plan, known: Iterable[str] = ()) -> list[Step]:
    """Order the steps so that every step comes after the steps it references.

    A reference to a step that is not in the plan raises KeyError naming the missing step;
    a cycle raises ValueError. known names steps outside the plan that already have evidence.
    """
    steps = plan.steps
    known = set(known)
    position: dict[str, int] = {}
    for i, step in enumerate(steps):
        if step.id in position:
            raise ValueError(f"step id {step.id} is used twice")
        position[step.id] = i
    waiting = [0] * len(steps)
    dependents: dict[str, list[int]] = {}
    for i, step in enumerate(steps):
        for ref in references(step.args):
            if ref in position:
                waiting[i] += 1
                dependents.setdefault(ref, []).append(i)
            elif ref not in known:
                raise KeyError(f"step {step.id} refers to {ref}, which is not in the plan")
    ready = [i for i, count in enumerate(waiting) if count == 0]
    heapq.heapify(ready)  # among ready steps, the planner's order wins
    order: list[Step] = []
    while ready:
        step = steps[heapq.heappop(ready)]
        order.append(step)
        for j in dependents.get(step.id, ()):
            waiting[j] -= 1
            if waiting[j] == 0:
                heapq.heappush(ready, j)
    if len(order) < len(steps):
        stuck = [step.id for i, step in enumerate(steps) if waiting[i]]
        raise ValueError(f"cyclic plan: {', '.join(stuck)} wait on each other")
    return order


def run_workers(
    plan: Plan, tools: ToolRegistry, known: dict[str, Evidence] | None = None
) -> dict[str, Evidence]:
    """Run every step once, in dependency order, and return the evidence of each, by step id.

    A step whose tool fails is failed: its evidence is the error text, and the Solver gets to see it.
    A step that references a failed or skipped step is skipped: its tool is never called and its
    evidence text is MISSING.

    known is evidence from an earlier run that the steps of this plan may reference; it is not
    returned and those steps do not run again.
    """
    seen: dict[str, Evidence] = dict(known or {})
    evidence: dict[str, Evidence] = {}
    for step in topological(plan, seen):
        if any(seen[ref].status != "ok" for ref in references(step.args)):
            result = Evidence("skipped", MISSING)
        else:
            result = tools.call(step.tool, **resolve_references(step.args, seen))
        seen[step.id] = evidence[step.id] = result
    return evidence
