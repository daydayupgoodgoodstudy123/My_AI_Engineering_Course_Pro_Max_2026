"""ReWOO end to end: the Planner writes the whole plan, the Workers gather evidence, the Solver answers."""
from __future__ import annotations

from dataclasses import dataclass

from .plan import Evidence, Plan
from .workers import ToolRegistry, run_workers


class ScriptedPlanner:
    """Stands in for the planner LLM: always returns the same plan."""

    def __init__(self, plan: Plan) -> None:
        self.plan = plan

    def plan_for(self, question: str) -> Plan:
        return self.plan


class ScriptedSolver:
    """Stands in for the solver LLM: fills a template such as "{E1} has {E3} people" with evidence text."""

    def __init__(self, template: str) -> None:
        self.template = template

    def solve(self, question: str, plan: Plan, evidence: dict[str, Evidence]) -> str:
        return self.template.format(**{step_id: ev.text for step_id, ev in evidence.items()})


@dataclass
class ReWOORun:
    question: str
    plan: Plan
    evidence: dict[str, Evidence]
    answer: str


def run_rewoo(question: str, planner: ScriptedPlanner, tools: ToolRegistry, solver: ScriptedSolver) -> ReWOORun:
    """One planner call, one worker per step, one solver call."""
    plan = planner.plan_for(question)
    evidence = run_workers(plan, tools)
    return ReWOORun(question, plan, evidence, solver.solve(question, plan, evidence))
