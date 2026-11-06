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
    raise NotImplementedError
