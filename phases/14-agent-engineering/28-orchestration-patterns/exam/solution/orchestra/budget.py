"""Grow a hierarchy only as deep as the supervisors' context budget forces it to be."""
from __future__ import annotations

from collections.abc import Sequence

from .topology import INHERIT, TeamSpec, Topology, WorkerSpec


def plan_hierarchy(
    workers: Sequence[WorkerSpec], budget: int, overhead: int, team_tokens: int
) -> Topology:
    """Arrange workers under supervisors so that every supervisor's routing prompt fits its budget.

    A supervisor's prompt costs overhead tokens plus one description per member: a worker's
    description costs worker.tokens, a sub-supervisor's costs team_tokens. A prompt fits when
    its cost is at most budget.

    Level 0 is the workers, in the order given. While a level does not fit under one
    supervisor, cut it, in order, into consecutive groups, each as long as will fit, and put
    every group of two or more items under a new supervisor. A group of one is carried up as it
    is, so no supervisor below the root has a single member. The new supervisors and the carried
    items, in order, form the next level. The first level that fits becomes the members of the
    root supervisor, named "root".

    The supervisors made on level k (counting from 1) are named f"L{k}-{j}", j = 0, 1, ... in
    order. A supervisor's keywords are its members' keywords, in member order, without repeats;
    its description is "Supervises " followed by its member names joined with ", "; its router
    is INHERIT. Topology.teams lists the supervisors in the order they are made, root last.

    Raises ValueError when there are no workers, when a worker's description cannot fit in a
    prompt (naming the worker), or when a level cannot be cut into fewer items.
    """
    if not workers:
        raise ValueError("no workers to arrange")
    for worker in workers:
        if overhead + worker.tokens > budget:
            raise ValueError(f"worker {worker.name!r} needs {worker.tokens} tokens, more than a prompt can hold")

    def cost(item: WorkerSpec | TeamSpec) -> int:
        return item.tokens if isinstance(item, WorkerSpec) else team_tokens

    def supervise(name: str, members: list[WorkerSpec | TeamSpec]) -> TeamSpec:
        keywords: list[str] = []
        for member in members:
            keywords += [k for k in member.keywords if k not in keywords]
        names = tuple(m.name for m in members)
        return TeamSpec(name, "Supervises " + ", ".join(names), names, tuple(keywords), INHERIT)

    teams: list[TeamSpec] = []
    level: list[WorkerSpec | TeamSpec] = list(workers)
    depth = 0
    while overhead + sum(cost(item) for item in level) > budget:
        depth += 1
        groups: list[list[WorkerSpec | TeamSpec]] = []
        group: list[WorkerSpec | TeamSpec] = []
        used = overhead
        for item in level:
            if group and used + cost(item) > budget:
                groups.append(group)
                group, used = [], overhead
            group.append(item)
            used += cost(item)
        groups.append(group)
        if len(groups) == len(level):
            raise ValueError(f"level {depth} cannot be cut into fewer than {len(level)} items")
        level = []
        made = 0
        for group in groups:
            if len(group) == 1:
                level.append(group[0])
                continue
            team = supervise(f"L{depth}-{made}", group)
            made += 1
            teams.append(team)
            level.append(team)
    teams.append(supervise("root", level))
    return Topology("root", tuple(workers), tuple(teams))
