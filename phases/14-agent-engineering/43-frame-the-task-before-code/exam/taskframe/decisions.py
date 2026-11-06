"""Decision coverage: has reconnaissance earned every decision the plan needs?"""
from __future__ import annotations

from dataclasses import dataclass

from .frame import TaskFrame
from .repo import Repo


@dataclass(frozen=True)
class Decision:
    key: str
    question: str


@dataclass(frozen=True)
class Assessment:
    status: str
    decisions: dict[str, str]
    questions: list[str]
    reads: list[str]


def assess(frame: TaskFrame, plan: list[Decision], delegated: set[str], repo: Repo) -> Assessment:
    """Say whether the agent may plan the change, must look further, or must ask first.

    delegated holds the decisions the task contract lets the agent make. Each planned
    decision gets the first of these that applies:

        "ask"          a human unknown names it, or a decidable unknown names it while the
                       contract does not delegate it (an agent cannot grant itself authority)
        "evidence"     a fact supports it and the fact's receipt resolves in repo
        "delegated"    the contract delegates it
        "investigate"  a discoverable unknown names it and says where to look (look_at)
        "deferred"     a deferred unknown names it and frame.non_goals lists the decision
        "open"         nothing covers it yet

    status is "ASK" when any decision is "ask", otherwise "INVESTIGATE" when any is
    "investigate" or "open", otherwise "READY". questions holds the questions of the
    unknowns that made a decision "ask", and reads the look_at of those that made one
    "investigate": both in plan order, then frame order, each once.

    An unknown of another kind, or one that names a decision outside the plan, raises
    ValueError.
    """
    raise NotImplementedError
