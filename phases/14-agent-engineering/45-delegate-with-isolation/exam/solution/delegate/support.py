"""Provided dependency validation; path claims are ordinary relative POSIX paths."""
from .model import WorkUnit


def safe_waves(units: list[WorkUnit]) -> tuple[list[list[str]], list[str]]:
    """Return waves and dependency issues without leaking scheduler exceptions.

    Repeated dependency references count once. Duplicate ids are checked by the
    caller; this helper returns no waves if ids repeat or references are invalid.
    """
    ids = [unit.id for unit in units]
    if len(ids) != len(set(ids)):
        return [], []
    remaining = {unit.id: set(unit.depends_on) for unit in units}
    issues = [f"unknown dependency: {node}: {dep}" for node, deps in remaining.items()
              for dep in sorted(deps - set(ids))]
    if issues:
        return [], issues
    completed = set()
    waves = []
    while remaining:
        ready = sorted(node for node, deps in remaining.items() if deps <= completed)
        if not ready:
            return [], ["dependency cycle"]
        waves.append(ready)
        completed.update(ready)
        for node in ready:
            del remaining[node]
    return waves, []


def prerequisite_sets(units: list[WorkUnit]) -> dict[str, set[str]]:
    """Return transitive prerequisite ids for a valid acyclic unique-id plan."""
    by_id = {unit.id: unit for unit in units}
    result = {}
    for unit in units:
        seen = set()
        stack = list(unit.depends_on)
        while stack:
            node = stack.pop()
            if node not in seen:
                seen.add(node)
                stack.extend(by_id[node].depends_on)
        result[unit.id] = seen
    return result
