"""Plan-and-Execute: ReWOO plus a replanner that patches only the part of the plan that went wrong."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from .agent import ScriptedPlanner, ScriptedSolver
from .plan import Evidence, Plan, Step, number, references
from .workers import ToolRegistry, run_workers

PATCH_REF = re.compile(r"#P(\d+)")
PATCH_ID = re.compile(r"P\d+")


@dataclass(frozen=True)
class Patch:
    """The replanner's fix.

    replaces names the steps whose evidence cannot be used. steps are the new steps, with local
    ids P1, P2, ...: a patch step refers to another patch step as #P<k> and to a kept step of the
    plan as #E<k>.
    """

    replaces: list[str]
    steps: list[Step]


class Replanner(Protocol):
    def review(self, question: str, plan: Plan, evidence: dict[str, Evidence]) -> Patch | None:
        """Look at the live steps and their evidence; return None to accept them, or a Patch."""


@dataclass
class Replanned:
    """The record of one Plan-and-Execute run."""

    plan: Plan  # every step ever planned: the planner's first, then each patch's, renumbered
    evidence: dict[str, Evidence]  # the evidence of every step in plan, dropped ones included
    dropped: set[str]  # the steps that patches invalidated
    answer: str


def plan_and_execute(
    question: str,
    planner: ScriptedPlanner,
    tools: ToolRegistry,
    replanner: Replanner,
    solver: ScriptedSolver,
    max_replans: int = 2,
) -> Replanned:
    """Plan once, run the plan, then let the replanner patch it, at most max_replans times.

    After every run the replanner reviews the live steps (those not dropped) and their evidence.
    It returns None to accept them, or a Patch. Applying a patch drops the steps it replaces and
    every step downstream of them: a step is downstream when it references a dropped step anywhere
    in its arguments, however deeply nested. A dropped step never runs again and its evidence is
    never shown again. Every other step keeps its evidence and does not run again either.

    The patch steps join the plan with new ids after the highest step number in the plan so far,
    dropped steps included (E<max+1>, E<max+2>, ... in the order they are listed). Their #P
    references are rewritten to the new ids, and then only they run. A patch that refers to a
    dropped step raises ValueError; one that refers to a step or a patch step that does not exist,
    or replaces a step that is not in the plan, raises KeyError.

    When the replanner accepts, or after max_replans patches, the Solver answers from the live
    steps and their evidence. max_replans below 0 raises ValueError.
    """
    if max_replans < 0:
        raise ValueError(f"max_replans must be 0 or more, got {max_replans}")
    plan = planner.plan_for(question)
    steps = list(plan.steps)
    evidence = run_workers(plan, tools)
    dropped: set[str] = set()
    for _ in range(max_replans):
        live = [step for step in steps if step.id not in dropped]
        patch = replanner.review(question, Plan(live), {s.id: evidence[s.id] for s in live})
        if patch is None:
            break
        added = _apply(patch, steps, dropped)
        kept = {step_id: ev for step_id, ev in evidence.items() if step_id not in dropped}
        evidence.update(run_workers(Plan(added), tools, known=kept))
        steps += added
    live = [step for step in steps if step.id not in dropped]
    answer = solver.solve(question, Plan(live), {s.id: evidence[s.id] for s in live})
    return Replanned(Plan(steps), evidence, dropped, answer)


def _apply(patch: Patch, steps: list[Step], dropped: set[str]) -> list[Step]:
    """Check a patch against the plan, drop what it invalidates, and return its renumbered steps."""
    ids = {step.id for step in steps}
    for step_id in patch.replaces:
        if step_id not in ids:
            raise KeyError(f"the patch replaces {step_id}, which is not in the plan")
        if step_id in dropped:
            raise ValueError(f"the patch replaces {step_id}, which was already dropped")
    gone = dropped | _downstream(steps, patch.replaces)
    local = [step.id for step in patch.steps]
    if len(set(local)) != len(local) or not all(PATCH_ID.fullmatch(pid) for pid in local):
        raise ValueError(f"patch steps need distinct ids P1, P2, ...; got {local}")
    first = max((number(step.id) for step in steps), default=0) + 1
    renamed = {pid: f"E{first + i}" for i, pid in enumerate(local)}
    added = []
    for step in patch.steps:
        for ref in references(step.args):
            if ref in gone:
                raise ValueError(f"patch step {step.id} refers to {ref}, which the patch drops")
            if ref not in ids:
                raise KeyError(f"patch step {step.id} refers to {ref}, which is not in the plan")
        added.append(Step(renamed[step.id], step.tool, _rename(step.args, renamed)))
    dropped |= gone
    return added


def _downstream(steps: list[Step], roots: list[str]) -> set[str]:
    """roots and every step that depends on one of them, directly or through other steps."""
    dependents: dict[str, list[str]] = {}
    for step in steps:
        for ref in references(step.args):
            dependents.setdefault(ref, []).append(step.id)
    found = set(roots)
    todo = list(roots)
    while todo:
        for step_id in dependents.get(todo.pop(), ()):
            if step_id not in found:
                found.add(step_id)
                todo.append(step_id)
    return found


def _rename(value: Any, renamed: dict[str, str]) -> Any:
    """Rewrite #P<k> references to the new step ids, at any depth of lists and dicts."""
    if isinstance(value, str):

        def new_id(match: re.Match) -> str:
            local = f"P{match.group(1)}"
            if local not in renamed:
                raise KeyError(f"#{local} is not a step of the patch")
            return f"#{renamed[local]}"

        return PATCH_REF.sub(new_id, value)
    if isinstance(value, list):
        return [_rename(item, renamed) for item in value]
    if isinstance(value, dict):
        return {key: _rename(item, renamed) for key, item in value.items()}
    return value
