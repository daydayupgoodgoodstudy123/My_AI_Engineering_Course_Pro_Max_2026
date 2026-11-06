"""Select a workbench pack without importing excluded project material."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    files: tuple[str, ...]
    requires: tuple[str, ...] = ()


def resolve_components(components: dict[str, Component], requested: list[str],
                       excluded: set[str]) -> list[str]:
    """Expand component references once, dependencies before dependants.

    Visit requests and each requires tuple in their given order. Reject missing
    components, cycles and any selected excluded file with ValueError; messages
    include the whole reference chain joined by ' -> '. For excluded files,
    append ': <file path>'. Do not inspect unrequested/unreachable components.
    """
    done = set()
    output = []

    def visit(name: str, chain: tuple[str, ...]) -> None:
        route = chain + (name,)
        if name in chain:
            raise ValueError("cycle: " + " -> ".join(route))
        if name in done:
            return
        if name not in components:
            raise ValueError("missing: " + " -> ".join(route))
        component = components[name]
        for path in component.files:
            if path in excluded:
                raise ValueError("excluded: " + " -> ".join(route) + ": " + path)
        for dependency in component.requires:
            visit(dependency, route)
        done.add(name)
        output.append(name)

    for name in requested:
        visit(name, ())
    return output
