"""Run a StateGraph with a checkpoint after every step: pause for a human, resume after a crash.

A session keeps its checkpoints (stategraph.checkpoint.Record) under a namespace. The root
graph's namespace is the session id. A subgraph node's namespace is its parent's namespace
followed by "|<node>:<step>", the node's name and the parent step it runs as, so a subgraph
two levels down in session s1 might checkpoint under "s1|review:2|legal:2".
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from .checkpoint import Record
from .effects import NodeContext, World
from .graph import END, HUMAN, PAUSE, START, State, StateGraph, Update


@dataclass(frozen=True)
class Checkpoint:
    """A session's whole state as of one step."""

    step: int
    node: str
    state: State


class PausedAtNode(Exception):
    """A node asked to pause. Its step is checkpointed, and resume() goes on from there."""

    def __init__(self, node: str, step: int, reason: str, namespace: str) -> None:
        super().__init__(node)
        self.node = node
        self.step = step
        self.reason = reason
        self.namespace = namespace


class Runner:
    def __init__(self, graph: StateGraph, checkpointer, world: World | None = None) -> None:
        self.graph = graph
        self.checkpointer = checkpointer
        self.world = world if world is not None else World()

    def run(self, session: str, inputs: State) -> State:
        """Start a session and run it to END; return the final state.

        The inputs are checkpointed as step 0 (node START), and every node that finishes is
        checkpointed as the next step. A node that puts PAUSE in its update is checkpointed
        without it, and then PausedAtNode is raised. A node that raises leaves no checkpoint.
        """
        state, step, node = self._begin(session, self.graph, inputs)
        return self._loop(session, self.graph, node, state, step)

    def resume(self, session: str, patch: Update | None = None) -> State:
        """Go on with a paused or crashed session and run it to END; return the final state.

        The run picks up at the node after the latest checkpointed node (step N+1), with the
        checkpointed state. A patch is a human edit: it is checkpointed as a step of its own
        (node HUMAN) and merged into the state before the next node is chosen. A session that
        stopped inside a subgraph node goes on inside it, and the patch goes there too.
        """
        state, step, node, inner = self._position(session, self.graph, patch)
        return self._loop(session, self.graph, node, state, step, inner)

    def load_state(self, session: str) -> Checkpoint | None:
        """The whole state as of the session's latest step; None for a session with no checkpoints.

        Changing the returned state does not change the checkpoints.
        """
        records = self.checkpointer.records(session)
        if not records:
            return None
        return Checkpoint(records[-1].step, records[-1].node, self._state_at(self.graph, records))

    def history(self, session: str) -> list[Checkpoint]:
        """The whole state as of every step of the session, in step order."""
        return [Checkpoint(r.step, r.node, copy.deepcopy(r.writes)) for r in self.checkpointer.records(session)]

    def replay(self, session: str) -> State:
        """Run a recorded session's nodes again, step by step, and return its final state.

        Each node step calls its node with the state as of the step before it and a
        NodeContext holding the step's recording, so nothing real is called. START and HUMAN
        steps are applied as recorded, and nothing is checkpointed. ReplayMismatch, with
        "step <n>" in its message, is raised for the first step whose calls differ from its
        recording or whose update, without the pause marker, differs from what the step wrote.
        """
        raise NotImplementedError

    def _begin(self, ns: str, graph: StateGraph, inputs: State) -> tuple[State, int, str]:
        state = self._commit(ns, graph, 0, START, {}, inputs)
        return state, 0, graph.next_node(START, state)

    def _position(self, ns: str, graph: StateGraph, patch: Update | None) -> tuple[State, int, str, Update | None]:
        """Where a stopped run goes on: (state, latest step, next node, patch for that node).

        The next node is the one after the latest checkpointed node (human edits are not
        nodes), chosen with the checkpointed state once the patch is applied.
        """
        records = self.checkpointer.records(ns)
        if not records:
            raise KeyError(ns)
        state, step = self._state_at(graph, records), records[-1].step
        here = next(r.node for r in reversed(records) if r.node != HUMAN)
        if _has_subgraphs(graph):
            inside = self._stopped_in(ns, graph, step + 1)
            if inside is not None:
                return state, step, inside, patch
        if patch is not None:
            step += 1
            state = self._commit(ns, graph, step, HUMAN, state, patch)
        return state, step, here, None

    def _loop(
        self, ns: str, graph: StateGraph, node: str, state: State, step: int, patch: Update | None = None
    ) -> State:
        while node is not None and node != END:
            step += 1
            target = graph.nodes[node]
            if isinstance(target, StateGraph):
                update, calls = self._subgraph(ns, node, step, target, state, patch), ()
            else:
                ctx = NodeContext(self.world)
                update, calls = target(state, ctx), ctx.calls
            patch = None
            state = self._commit(ns, graph, step, node, state, update or {}, calls)
            if state.get(PAUSE):
                reason = state.pop(PAUSE)
                raise PausedAtNode(node, step, reason, ns)
            node = graph.next_node(node, state)
        return state

    def _commit(
        self, ns: str, graph: StateGraph, step: int, node: str, state: State, update: Update, calls=()
    ) -> State:
        """Checkpoint one step and return the state after it."""
        state = graph.merge(state, update)
        self.checkpointer.put(ns, Record(step, node, state, tuple(calls)))
        return state

    def _state_at(self, graph: StateGraph, records: list[Record]) -> State:
        """The whole state as of the last of these records: their writes folded in step order
        through the graph's reducers. The result shares nothing with the records."""
        return copy.deepcopy(records[-1].writes)

    def _subgraph(
        self, ns: str, node: str, step: int, graph: StateGraph, state: State, patch: Update | None
    ) -> Update:
        """Run the subgraph that node `node` holds, as step `step` of namespace `ns`, to its END.
        Return the update the parent gets for the node.

        The subgraph checkpoints under the namespace "<ns>|<node>:<step>". It starts from the
        parent's state, checkpointed as its START step, unless that namespace already has
        checkpoints: then the session stopped inside it, and it resumes after its latest
        checkpoint the way resume() does, with `patch` as the human edit. A pause inside it
        raises PausedAtNode with its namespace, and the parent writes no checkpoint for the
        node. The parent's update is every write the subgraph's steps made after START, node
        steps and human edits alike, folded in step order through the subgraph's reducers.
        """
        raise NotImplementedError

    def _stopped_in(self, ns: str, graph: StateGraph, step: int) -> str | None:
        """The subgraph node of `graph` that was running as step `step` of namespace `ns`
        when the session stopped (its namespace has checkpoints), or None."""
        raise NotImplementedError


def _has_subgraphs(graph: StateGraph) -> bool:
    return any(isinstance(node, StateGraph) for node in graph.nodes.values())
