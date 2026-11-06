"""The graph: nodes, direct and conditional edges, and the reducers that merge updates into state."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

State = dict[str, Any]
Update = dict[str, Any]
Router = Callable[[State], str]
Reducer = Callable[[Any, Any], Any]

START = "__start__"  # node name of step 0, the checkpoint that holds a session's inputs
END = "__end__"
HUMAN = "__human__"  # node name of a checkpoint that holds a human edit
PAUSE = "_pause_reason"  # a node puts this key in its update to pause the run after it


class GraphError(Exception):
    """The graph has no way on from a node."""


def append(current: list, new: list) -> list:
    """Reducer for list channels: the update's items go after the current ones."""
    return [*current, *new]


@dataclass
class Edge:
    """An edge out of a node. A conditional edge is taken when the router returns its label."""

    dst: str
    router: Router | None = None
    label: str | None = None


class StateGraph:
    """Nodes, edges and per-channel reducers.

    A node is fn(state, ctx) -> update, where the update is a dict of the channels the node
    writes and ctx is the node's stategraph.effects.NodeContext. A node can also be another
    StateGraph, which then runs as a subgraph.
    """

    def __init__(self, reducers: dict[str, Reducer] | None = None) -> None:
        self.nodes: dict[str, Any] = {}
        self.edges: dict[str, list[Edge]] = {}
        self.reducers: dict[str, Reducer] = dict(reducers or {})

    def add_node(self, name: str, node: Any) -> None:
        self.nodes[name] = node

    def set_entry(self, name: str) -> None:
        self.add_edge(START, name)

    def add_edge(self, src: str, dst: str) -> None:
        self.edges.setdefault(src, []).append(Edge(dst))

    def add_conditional_edges(self, src: str, router: Router, targets: dict[str, str]) -> None:
        for label, dst in targets.items():
            self.edges.setdefault(src, []).append(Edge(dst, router, label))

    def next_node(self, node: str, state: State) -> str:
        """The node that runs after `node` (END when the graph is done).

        A direct edge is followed as it is. Otherwise the node's router is called exactly once
        with the state, and its label picks the target. A label without a target, or a node
        with no edge out of it, raises GraphError naming the node.
        """
        for edge in self.edges.get(node, []):
            if edge.router is None or edge.router(state) == edge.label:
                return edge.dst
        return None

    def merge(self, state: State, update: Update) -> State:
        """The state after an update, as a new dict; `state` itself is not changed.

        A channel with a reducer that already holds a value becomes reducer(current, new).
        Any other channel takes the update's value.
        """
        merged = dict(state)
        for channel, value in update.items():
            reducer = self.reducers.get(channel)
            merged[channel] = reducer(merged[channel], value) if reducer and channel in merged else value
        return merged
