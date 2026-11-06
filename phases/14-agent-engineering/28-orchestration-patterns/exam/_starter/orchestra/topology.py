"""The orchestration topology as configuration: workers, teams, and a JSON snapshot of both."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class _Inherit:
    """Marker for a team that takes its router from the team above it."""

    _instance: _Inherit | None = None

    def __new__(cls) -> _Inherit:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "INHERIT"


INHERIT = _Inherit()


@dataclass(frozen=True)
class WorkerSpec:
    """A specialist. tokens is what its description costs in a supervisor's prompt."""

    name: str
    description: str
    tokens: int
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamSpec:
    """A supervisor and the members it routes to, in routing order.

    router is the model name of an LLM router; None routes by keyword with no LLM at all
    (a deterministic Flow); INHERIT uses whatever the team above uses.
    """

    name: str
    description: str
    members: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    router: str | None | _Inherit = INHERIT


@dataclass(frozen=True)
class Topology:
    root: str
    workers: tuple[WorkerSpec, ...]
    teams: tuple[TeamSpec, ...]

    def find(self, name: str) -> WorkerSpec | TeamSpec:
        """The worker or team with this name. Unknown names raise KeyError."""
        for node in (*self.workers, *self.teams):
            if node.name == name:
                return node
        raise KeyError(name)


def save_topology(path: str | os.PathLike, topology: Topology) -> None:
    """Write the topology as one JSON snapshot, replacing any earlier snapshot atomically.

    Snapshot layout:
        {"format": 1, "root": name,
         "workers": [{"name", "description", "tokens", "keywords"}, ...],
         "teams": [{"name", "description", "members", "keywords", "router"}, ...]}
    Lists keep the topology's order. "router" holds a model name or null; it is left out when
    the team inherits its router.

    The JSON goes to a temporary file in the snapshot's own directory, which then replaces the
    snapshot with os.replace, so a crash leaves either the old snapshot or the new one. A failed
    save leaves no temporary file behind.

    Raises ValueError, before writing anything, when a name is used twice (workers and teams
    share one namespace), when a team lists a member that does not exist, or when the root is
    not a team.
    """
    raise NotImplementedError


def load_topology(path: str | os.PathLike) -> Topology:
    """Read a snapshot written by save_topology (or by hand, in the same layout)."""
    raise NotImplementedError
