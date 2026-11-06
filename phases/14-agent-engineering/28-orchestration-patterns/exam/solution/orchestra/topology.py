"""The orchestration topology as configuration: workers, teams, and a JSON snapshot of both."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

FORMAT = 1


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


def _validate(topology: Topology) -> None:
    names = [node.name for node in (*topology.workers, *topology.teams)]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"names used twice: {duplicates}")
    known = set(names)
    for team in topology.teams:
        missing = [m for m in team.members if m not in known]
        if missing:
            raise ValueError(f"team {team.name!r} lists unknown members {missing}")
    if topology.root not in {t.name for t in topology.teams}:
        raise ValueError(f"root {topology.root!r} is not a team")


def _team_to_json(team: TeamSpec) -> dict:
    data = {
        "name": team.name,
        "description": team.description,
        "members": list(team.members),
        "keywords": list(team.keywords),
    }
    if team.router is not INHERIT:
        data["router"] = team.router
    return data


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
    _validate(topology)
    data = {
        "format": FORMAT,
        "root": topology.root,
        "workers": [
            {"name": w.name, "description": w.description, "tokens": w.tokens, "keywords": list(w.keywords)}
            for w in topology.workers
        ],
        "teams": [_team_to_json(t) for t in topology.teams],
    }
    target = Path(path)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_topology(path: str | os.PathLike) -> Topology:
    """Read a snapshot written by save_topology (or by hand, in the same layout)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    workers = tuple(
        WorkerSpec(w["name"], w["description"], w["tokens"], tuple(w["keywords"])) for w in data["workers"]
    )
    teams = tuple(
        TeamSpec(
            t["name"],
            t["description"],
            tuple(t["members"]),
            tuple(t["keywords"]),
            t["router"] if "router" in t else INHERIT,
        )
        for t in data["teams"]
    )
    return Topology(data["root"], workers, teams)
