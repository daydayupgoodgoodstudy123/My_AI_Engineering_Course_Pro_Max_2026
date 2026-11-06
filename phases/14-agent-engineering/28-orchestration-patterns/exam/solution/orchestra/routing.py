"""Deterministic routing down a nested topology, backing out of dead ends and tracing every pick."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .topology import Topology, WorkerSpec

_WORD = re.compile(r"\w+")


def tokenize(text: str) -> set[str]:
    """The words of a text, in lower case. A word is a run of letters, digits and underscores."""
    return set(_WORD.findall(text.lower()))


@dataclass(frozen=True)
class Route:
    """Where a task ended up. worker is None when the task stays unresolved; path is then empty.

    trace is for people to read, one line at a time, so comparisons and the repr leave it out:
    two routes that reach the same worker by the same path at the same cost are equal.
    """

    worker: str | None
    path: tuple[str, ...]
    ops: int
    backtracks: int
    trace: tuple[str, ...] = field(default=(), compare=False, repr=False)


class _GiveUp(Exception):
    pass


def route(topology: Topology, task: str, max_backtracks: int = 3) -> Route:
    """Send a task down the topology by keyword, from the root team to one worker.

    A member matches the task when one of its keywords, in lower case, is one of tokenize(task).
    Asked for a pick, a team offers its next member, in member order, that matches and has not
    been tried by this team yet. A picked worker takes the task. A picked team is entered and
    asked in turn. A team with nothing left to offer is a dead end: the task goes back to the
    team above, which is asked for its next pick; each such return is one backtrack. A team that
    came up empty is passed over from then on: it is never offered or entered again for this
    task, even where it also sits under another team.

    ops counts every time a team is asked for a pick, including the time it has nothing left,
    plus one for the worker that takes the task. path runs from the root to that worker.

    trace has one line for every time a team is asked for a pick, in order, whether or not the
    task is resolved: two spaces for every team above the asked team on the path, then
    "<team> -> <member>", or "<team> -> none" when it has nothing left to offer. The pick a team
    is asked for right after a backtrack to it ends with ", back from <team>", naming the team
    the task came back from.

    The task stays unresolved when the root has nothing left to offer, or when one more
    backtrack than max_backtracks would be needed. A team that is reached again while it is
    still on the path raises ValueError.
    """
    words = tokenize(task)
    failed: set[str] = set()
    path: list[str] = []
    trace: list[str] = []
    ops = 0
    backtracks = 0

    def matches(name: str) -> bool:
        return any(k.lower() in words for k in topology.find(name).keywords)

    def visit(team_name: str) -> str | None:
        nonlocal ops, backtracks
        if team_name in path:
            raise ValueError(f"team {team_name!r} contains itself: {' > '.join(path)} > {team_name}")
        path.append(team_name)
        members = topology.find(team_name).members
        position = 0
        back_from: str | None = None
        while True:
            ops += 1
            pick = None
            while position < len(members):
                name = members[position]
                position += 1
                if name not in failed and matches(name):
                    pick = name
                    break
            indent = "  " * (len(path) - 1)
            note = f", back from {back_from}" if back_from else ""
            if pick is None:
                trace.append(f"{indent}{team_name} -> none{note}")
                failed.add(team_name)
                path.pop()
                return None
            trace.append(f"{indent}{team_name} -> {pick}{note}")
            if isinstance(topology.find(pick), WorkerSpec):
                ops += 1
                path.append(pick)
                return pick
            if visit(pick) is not None:
                return path[-1]
            if backtracks == max_backtracks:
                raise _GiveUp
            backtracks += 1
            back_from = pick

    try:
        worker = visit(topology.root)
    except _GiveUp:
        worker = None
    if worker is None:
        return Route(None, (), ops, backtracks, tuple(trace))
    return Route(worker, tuple(path), ops, backtracks, tuple(trace))
