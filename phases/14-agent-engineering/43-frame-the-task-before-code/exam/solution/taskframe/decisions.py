"""Decision coverage: has reconnaissance earned every decision the plan needs?"""
from __future__ import annotations

from dataclasses import dataclass

from .frame import UNKNOWN_KINDS, TaskFrame, receipt_problem
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
    keys = [decision.key for decision in plan]
    for unknown in frame.unknowns:
        if unknown.kind not in UNKNOWN_KINDS:
            raise ValueError(f"{unknown.question!r}: unknown kind {unknown.kind!r}")
        if unknown.decision not in keys:
            raise ValueError(f"{unknown.question!r} names {unknown.decision!r}, which is not planned")

    decisions: dict[str, str] = {}
    questions: list[str] = []
    reads: list[str] = []
    for key in keys:
        mine = [u for u in frame.unknowns if u.decision == key]
        asks = [u for u in mine if u.kind == "human" or (u.kind == "decidable" and key not in delegated)]
        looks = [u for u in mine if u.kind == "discoverable" and u.look_at.strip()]
        if asks:
            decisions[key] = "ask"
            _extend_once(questions, [u.question for u in asks])
        elif any(key in f.supports and receipt_problem(f.evidence, repo) is None for f in frame.facts):
            decisions[key] = "evidence"
        elif key in delegated:
            decisions[key] = "delegated"
        elif looks:
            decisions[key] = "investigate"
            _extend_once(reads, [u.look_at for u in looks])
        elif key in frame.non_goals and any(u.kind == "deferred" for u in mine):
            decisions[key] = "deferred"
        else:
            decisions[key] = "open"

    covered = set(decisions.values())
    if "ask" in covered:
        status = "ASK"
    elif covered & {"investigate", "open"}:
        status = "INVESTIGATE"
    else:
        status = "READY"
    return Assessment(status, decisions, questions, reads)


def _extend_once(items: list[str], new: list[str]) -> None:
    for item in new:
        if item not in items:
            items.append(item)
