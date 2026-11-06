"""Workers: run a plan's steps in dependency order and collect their evidence."""
from __future__ import annotations

from typing import Any, Callable

from .plan import REF, Evidence, Plan, Step


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
    if not isinstance(value, str):
        return value
    return REF.sub(lambda m: evidence[f"E{m.group(1)}"].text, value)


def topological(plan: Plan) -> list[Step]:
    """Order the steps so that every step comes after the steps it references.

    A reference to a step that is not in the plan raises KeyError naming the missing step;
    a cycle raises ValueError.
    """
    resolved: list[Step] = []
    known: set[str] = set()
    pending = list(plan.steps)
    while pending:
        progress = False
        rest: list[Step] = []
        for step in pending:
            refs = REF.findall(str(step.args))
            if all(f"E{r}" in known for r in refs):
                resolved.append(step)
                known.add(step.id)
                progress = True
            else:
                rest.append(step)
        if not progress:
            raise ValueError("cyclic plan")
        pending = rest
    return resolved


def run_workers(plan: Plan, tools: ToolRegistry) -> dict[str, Evidence]:
    """Run every step once, in dependency order, and return the evidence of each, by step id.

    A step whose tool fails is failed: its evidence is the error text, and the Solver gets to see it.
    A step that references a failed or skipped step is skipped: its tool is never called and its
    evidence text is MISSING.
    """
    evidence: dict[str, Evidence] = {}
    for step in topological(plan):
        args = {key: resolve_references(value, evidence) for key, value in step.args.items()}
        evidence[step.id] = tools.call(step.tool, **args)
    return evidence
