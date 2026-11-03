"""Composite tools: a tool built from other tools can do whatever they can do."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .tools import Tool


@dataclass(frozen=True)
class Effect:
    kind: str  # "pure" or "consequential"
    path: tuple[str, ...]  # why it is consequential (see classify); () when pure
    actions: tuple[str, ...]  # the tools declared consequential that it can set off, sorted, each once


def classify(tools: Iterable[Tool]) -> dict[str, Effect]:
    """The effective kind of every tool, following the calls of composite tools.

    A tool is consequential if it is declared consequential, or if any tool it can reach
    through calls is. path says why: it starts at the tool and follows calls down to a
    tool declared consequential, stopping at the first one. When there are several such
    paths, path is the alphabetically first, comparing paths name by name.

    The call graph has no cycles. A call to a tool that is not in tools raises ValueError
    naming it.
    """
    by_name = {tool.name: tool for tool in tools}
    for tool in by_name.values():
        unknown = sorted(set(tool.calls) - by_name.keys())
        if unknown:
            raise ValueError(f"{tool.name} calls unknown tools: {', '.join(unknown)}")
    effects: dict[str, Effect] = {}

    def visit(name: str) -> Effect:
        if name not in effects:  # worked out once, however many paths lead here
            tool = by_name[name]
            below = [visit(callee) for callee in sorted(set(tool.calls))]
            actions = {action for effect in below for action in effect.actions}
            if tool.consequential:
                actions.add(name)
                path: tuple[str, ...] = (name,)
            else:
                # Paths from here differ first in the callee, so the alphabetically
                # first path goes through the first callee (in name order) that has one.
                path = next(((name, *effect.path) for effect in below if effect.path), ())
            effects[name] = Effect("consequential" if path else "pure", path, tuple(sorted(actions)))
        return effects[name]

    return {name: visit(name) for name in by_name}
