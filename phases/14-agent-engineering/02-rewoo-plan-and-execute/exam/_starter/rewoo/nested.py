"""Nested sub-plans, expanded into one flat plan that the workers can run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from .plan import Plan, Step


@dataclass(frozen=True)
class SubPlan:
    """A step whose work is a plan of its own.

    Its steps live in their own #E namespace: inside, #E1 means the sub-plan's own E1. Evidence
    from the enclosing plan is visible only through imports, which map a local id to an id of the
    enclosing plan: imports={"E1": "E4"} makes #E1 inside mean the enclosing plan's E4. The
    evidence of the step named by output is the sub-plan's evidence in the enclosing plan.
    """

    id: str
    steps: list[Union[Step, "SubPlan"]]
    output: str
    imports: dict[str, str] = field(default_factory=dict)


def flatten(steps: list[Step | SubPlan]) -> Plan:
    """Expand nested sub-plans into one flat plan.

    Top-level steps keep their ids. Expanding a sub-plan first gives each of its steps a flat id,
    in the order they are listed: the output step takes the sub-plan's own flat id, and every other
    step the next free number, counting up from the highest top-level step number. Then the steps
    are expanded one by one in that order, so a nested sub-plan numbers its own steps when its turn
    comes. References are rewritten to the flat ids, and a sub-plan's steps take its place in the
    flat plan.

    Raises ValueError for an empty sub-plan, an output that is not one of its steps, an import
    named like one of its steps, or an id used twice in one plan; KeyError for an import of an id
    the enclosing plan does not have, or a reference to an id that is neither a step of its own
    plan nor an import.
    """
    raise NotImplementedError
