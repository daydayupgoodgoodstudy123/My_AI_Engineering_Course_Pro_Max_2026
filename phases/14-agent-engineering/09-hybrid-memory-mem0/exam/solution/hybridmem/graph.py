"""Mem0g-style graph store: typed edges, each with the interval over which it held.

When a new edge contradicts the current one (same subject and relation, another object),
the old edge is closed, never deleted, so questions about the past can still be answered.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Edge:
    subject: str
    relation: str
    obj: str
    rid: str  # the memory that asserted the edge
    valid_from: float
    weight: float = 1.0
    valid_to: float | None = None

    @property
    def valid(self) -> bool:
        """True until a contradicting edge closes this one."""
        return self.valid_to is None


class GraphStore:
    def __init__(self) -> None:
        self._edges: list[Edge] = []
        self._current: dict[tuple[str, str], Edge] = {}

    def current(self, subject: str, relation: str) -> Edge | None:
        """The edge that holds now for (subject, relation), or None."""
        return self._current.get((subject, relation))

    def add_edge(self, subject: str, relation: str, obj: str, *, rid: str, at: float, weight: float = 1.0) -> Edge:
        """Assert subject --relation--> obj at time `at`, and return the edge that holds now.

        Relations are single-valued. Another object for the same subject and relation
        contradicts the current edge: that edge is closed (valid_to = at) and kept, and the
        new edge holds from `at`. Asserting the object that already holds changes nothing
        and returns the current edge.
        """
        old = self.current(subject, relation)
        if old is not None:
            if old.obj == obj:
                return old
            old.valid_to = float(at)
        edge = Edge(subject, relation, obj, rid, float(at), float(weight))
        self._edges.append(edge)
        self._current[(subject, relation)] = edge
        return edge

    def restore(self, edge: Edge) -> None:
        """Put back a saved edge exactly as it was, with no conflict check. Used when loading."""
        self._edges.append(edge)
        if edge.valid:
            self._current[(edge.subject, edge.relation)] = edge

    def history(self, subject: str, relation: str) -> list[Edge]:
        """Every edge ever asserted for (subject, relation), in the order they were asserted."""
        return [e for e in self._edges if e.subject == subject and e.relation == relation]

    def neighbors(self, subject: str, valid_only: bool = True) -> list[Edge]:
        return [e for e in self._edges if e.subject == subject and (e.valid or not valid_only)]

    def all_edges(self) -> list[Edge]:
        """Every edge in the order they were asserted, closed ones included."""
        return list(self._edges)
