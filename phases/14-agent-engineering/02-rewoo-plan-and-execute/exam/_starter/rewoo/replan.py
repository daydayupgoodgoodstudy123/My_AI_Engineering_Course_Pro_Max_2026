"""Plan-and-Execute: ReWOO plus a replanner that patches only the part of the plan that went wrong."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .agent import ScriptedPlanner, ScriptedSolver
from .plan import Evidence, Plan, Step
from .workers import ToolRegistry


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
    raise NotImplementedError
