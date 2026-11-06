"""Point-in-time questions over the graph: what held at a moment, and how two nodes were connected then."""
from __future__ import annotations

from dataclasses import dataclass

from .graph import Edge, GraphStore


@dataclass(frozen=True)
class Path:
    weight: float
    edges: tuple[Edge, ...]


def value_at(graph: GraphStore, subject: str, relation: str, at: float) -> str | None:
    """The object of (subject, relation) at time `at`, or None: "what was the user's city in March?"

    An edge holds over [valid_from, valid_to): from the moment it was asserted up to, but not
    including, the moment a contradicting edge closed it. valid_to None means it still holds.
    """
    raise NotImplementedError


def paths(graph: GraphStore, source: str, target: str, *, at: float, max_hops: int = 3) -> list[Path]:
    """Every way source was connected to target at time `at`.

    A path follows edges from subject to object, uses only edges that held at `at` (as in
    value_at), never visits a node twice and has at most max_hops edges. Its weight is the
    product of its edges' weights. Best first: higher weight, then fewer hops, then the hops'
    (relation, object) pairs in alphabetical order, hop by hop.
    """
    raise NotImplementedError
