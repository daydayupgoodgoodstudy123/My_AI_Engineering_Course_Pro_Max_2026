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
    raise NotImplementedError
