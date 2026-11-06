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
    for edge in graph.history(subject, relation):
        if _holds(edge, at):
            return edge.obj
    return None


def paths(graph: GraphStore, source: str, target: str, *, at: float, max_hops: int = 3) -> list[Path]:
    """Every way source was connected to target at time `at`.

    A path follows edges from subject to object, uses only edges that held at `at` (as in
    value_at), never visits a node twice and has at most max_hops edges. Its weight is the
    product of its edges' weights. Best first: higher weight, then fewer hops, then the hops'
    (relation, object) pairs in alphabetical order, hop by hop.
    """
    out: dict[str, list[Edge]] = {}
    for edge in graph.all_edges():
        if _holds(edge, at):
            out.setdefault(edge.subject, []).append(edge)
    found: list[Path] = []

    def walk(node: str, trail: tuple[Edge, ...], seen: frozenset[str], weight: float) -> None:
        for edge in out.get(node, ()):
            if edge.obj in seen:
                continue
            step = trail + (edge,)
            w = weight * edge.weight
            if edge.obj == target:
                found.append(Path(w, step))
            elif len(step) < max_hops:
                walk(edge.obj, step, seen | {edge.obj}, w)

    walk(source, (), frozenset({source}), 1.0)
    found.sort(key=lambda p: (-p.weight, len(p.edges), [(e.relation, e.obj) for e in p.edges]))
    return found


def _holds(edge: Edge, at: float) -> bool:
    return edge.valid_from <= at and (edge.valid_to is None or at < edge.valid_to)
