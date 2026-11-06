"""Nested sub-plans, expanded into one flat plan that the workers can run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

from .plan import REF, Plan, Step, number


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
    top = _ids(steps)
    counter = max(number(step_id) for step_id in top)
    flat: list[Step] = []

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"E{counter}"

    def expand(item: Step | SubPlan, flat_id: str, scope: dict[str, str]) -> None:
        if isinstance(item, Step):
            flat.append(Step(flat_id, item.tool, _rewrite(item.args, scope)))
            return
        own = _ids(item.steps)
        if item.output not in own:
            raise ValueError(f"sub-plan {item.id} outputs {item.output}, which is not one of its steps")
        inner: dict[str, str] = {}
        for local, outer in item.imports.items():
            if local in own:
                raise ValueError(f"sub-plan {item.id} imports {local}, which is also one of its steps")
            if outer not in scope:
                raise KeyError(f"sub-plan {item.id} imports {outer}, which its enclosing plan does not have")
            inner[local] = scope[outer]
        for step in item.steps:
            inner[step.id] = flat_id if step.id == item.output else next_id()
        for step in item.steps:
            expand(step, inner[step.id], inner)

    top_scope = {step_id: step_id for step_id in top}
    for item in steps:
        expand(item, item.id, top_scope)
    return Plan(flat)


def _ids(steps: list[Step | SubPlan]) -> list[str]:
    if not steps:
        raise ValueError("a plan needs at least one step")
    ids = [step.id for step in steps]
    if len(set(ids)) != len(ids):
        raise ValueError(f"step ids repeat: {ids}")
    for step_id in ids:
        number(step_id)
    return ids


def _rewrite(value: Any, scope: dict[str, str]) -> Any:
    """Rewrite every #E reference through scope, all at once, at any depth of lists and dicts."""
    if isinstance(value, str):

        def flat_ref(match) -> str:
            name = f"E{match.group(1)}"
            if name not in scope:
                raise KeyError(f"#{name} is neither a step of this plan nor an import")
            return f"#{scope[name]}"

        return REF.sub(flat_ref, value)
    if isinstance(value, list):
        return [_rewrite(item, scope) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite(item, scope) for key, item in value.items()}
    return value
