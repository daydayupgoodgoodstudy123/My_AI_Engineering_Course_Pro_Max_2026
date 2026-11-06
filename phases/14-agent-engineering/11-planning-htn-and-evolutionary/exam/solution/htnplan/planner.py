"""ChatHTN-style planning: symbolic HTN search that asks an LLM only where the library runs out."""
from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass, field

from .domain import Method, Operator
from .llm import ScriptedLLM
from .tree import LLM, Node, leaves

Found = tuple[Node, frozenset[str]]  # a decomposition, and the state it leaves behind


@dataclass
class HTNPlanner:
    """A hybrid HTN planner in the ChatHTN pattern.

    The symbolic layer owns correctness. An LLM reply is only a candidate decomposition: it is
    used, and learned into cached_methods, only once it expands into operators whose
    preconditions hold one after another.
    """

    operators: dict[str, Operator]
    methods: dict[str, list[Method]]
    llm: ScriptedLLM
    max_depth: int = 12
    cached_methods: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def plan(self, task: str, state: Set[str]) -> list[str] | None:
        """The operators that carry out task from state, in order, or None if there is no plan.

        A primitive task is its own operator, if the operator's preconditions hold. A compound
        task tries these in order until one expands into a plan: each library method whose
        preconditions hold, in library order; the decomposition learned for the task earlier
        (cached_methods); a new decomposition from the LLM. An LLM reply that names anything
        other than an operator or a library task is rejected without being expanded. A reply is
        learned only once it has expanded, and then replaces what was learned for the task
        before. Decompositions nest at most max_depth levels below task. Within one call, once
        a task has failed from a state it is not tried from that state again. The state passed
        in is not changed.
        """
        tree = self.plan_tree(task, state)
        return None if tree is None else leaves(tree)

    def plan_tree(self, task: str, state: Set[str]) -> Node | None:
        """The decomposition tree behind plan(), or None if there is no plan.

        Every compound task in the tree records the method that worked for it: the name of a
        library method, or "llm" for a decomposition from the LLM, asked now or learned
        earlier. The leaves, left to right, are exactly what plan() returns. Planning, and
        what it learns, work as in plan().
        """
        found = self._plan(task, frozenset(state), 0, set())
        return None if found is None else found[0]

    def _plan(self, task: str, state: frozenset[str], depth: int, failed: set) -> Found | None:
        if depth > self.max_depth:
            return None
        if task in self.operators:
            op = self.operators[task]
            return (Node(task), frozenset(op.apply(state))) if op.applicable(state) else None
        if (task, state) in failed:
            return None
        for method in self.methods.get(task, []):
            if method.applicable(state):
                found = self._expand(task, method.name, method.subtasks, state, depth, failed)
                if found is not None:
                    return found
        learned = self.cached_methods.get(task)
        if learned is not None:
            found = self._expand(task, LLM, learned, state, depth, failed)
            if found is not None:
                return found
        suggested = self.llm.decompose(task, set(state))
        if suggested is not None and all(s in self.operators or s in self.methods for s in suggested):
            found = self._expand(task, LLM, tuple(suggested), state, depth, failed)
            if found is not None:
                self.cached_methods[task] = tuple(suggested)
                return found
        failed.add((task, state))  # this search will not try task from this state again
        return None

    def _expand(
        self,
        task: str,
        method: str,
        subtasks: tuple[str, ...],
        state: frozenset[str],
        depth: int,
        failed: set,
    ) -> Found | None:
        """Plan the subtasks in turn, each from the state the ones before it leave behind."""
        children = []
        for subtask in subtasks:
            found = self._plan(subtask, state, depth + 1, failed)
            if found is None:
                return None
            child, state = found
            children.append(child)
        return Node(task, method, tuple(children)), state
