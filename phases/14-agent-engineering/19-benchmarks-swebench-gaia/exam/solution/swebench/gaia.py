"""Grade a GAIA-style question by its decomposition: how long a tool chain it needs, across which modalities.

A plan is a tree of steps:
    {"tool": name, "input": modality}   one tool call that reads one modality (web, pdf, image, ...)
    {"think": note}                     a reasoning step, no tool
    {"seq": [plan, ...]}                steps that depend on each other, in order
    {"par": [plan, ...]}                independent sub-questions that can run at the same time
A bare list is shorthand for {"seq": list}.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Plan = Any


@dataclass(frozen=True)
class Difficulty:
    level: int
    chain: int
    modalities: tuple[str, ...]


def gaia_level(plan: Plan) -> Difficulty:
    """Difficulty of a plan.

    A path is one way through the plan: a seq goes through each of its steps in order, a par
    through exactly one of its branches. chain is the most tool calls on any path. modalities
    are the distinct inputs of every tool call in the plan, sorted.

    Level 3 when some path has at least 5 tool calls that read at least 2 different modalities
    (a long tool chain across modalities). Otherwise level 2 when chain is at least 2 or the plan
    reads at least 2 modalities. Otherwise level 1.
    A node that is not one of the shapes above, or a seq or par with no steps, raises ValueError.
    """
    paths = _paths(plan)
    chain = max(paths.values())
    modalities = tuple(sorted(set().union(*paths)))
    if any(calls >= 5 and len(mods) >= 2 for mods, calls in paths.items()):
        level = 3
    elif chain >= 2 or len(modalities) >= 2:
        level = 2
    else:
        level = 1
    return Difficulty(level, chain, modalities)


def _paths(node: Plan) -> dict[frozenset[str], int]:
    """For every set of modalities some path reads, the most tool calls on such a path."""
    if isinstance(node, list):
        node = {"seq": node}
    if not isinstance(node, dict):
        raise ValueError(f"not a plan step: {node!r}")
    keys = set(node)
    if keys == {"tool", "input"} and isinstance(node["input"], str):
        return {frozenset([node["input"]]): 1}
    if keys == {"think"}:
        return {frozenset(): 0}
    if keys in ({"seq"}, {"par"}) and isinstance(next(iter(node.values())), list):
        (kind, steps), = node.items()
        if not steps:
            raise ValueError(f"empty {kind}")
        parts = [_paths(step) for step in steps]
        if kind == "par":
            merged: dict[frozenset[str], int] = {}
            for part in parts:
                for mods, calls in part.items():
                    merged[mods] = max(calls, merged.get(mods, calls))
            return merged
        acc = {frozenset(): 0}
        for part in parts:
            nxt: dict[frozenset[str], int] = {}
            for m1, c1 in acc.items():
                for m2, c2 in part.items():
                    mods = m1 | m2
                    nxt[mods] = max(c1 + c2, nxt.get(mods, c1 + c2))
            acc = nxt
        return acc
    raise ValueError(f"not a plan step: {node!r}")
