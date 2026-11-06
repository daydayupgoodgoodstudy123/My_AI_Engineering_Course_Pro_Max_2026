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
    raise NotImplementedError
