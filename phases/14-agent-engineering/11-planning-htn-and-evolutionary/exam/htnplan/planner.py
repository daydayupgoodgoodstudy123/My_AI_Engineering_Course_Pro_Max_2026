"""ChatHTN-style planning: symbolic HTN search that asks an LLM only where the library runs out."""
from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass, field

from .domain import Method, Operator
from .llm import ScriptedLLM
from .tree import Node


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
        return self._plan(task, set(state), 0)

    def plan_tree(self, task: str, state: Set[str]) -> Node | None:
        """The decomposition tree behind plan(), or None if there is no plan.

        Every compound task in the tree records the method that worked for it: the name of a
        library method, or "llm" for a decomposition from the LLM, asked now or learned
        earlier. The leaves, left to right, are exactly what plan() returns. Planning, and
        what it learns, work as in plan().
        """
        raise NotImplementedError

    def _plan(self, task: str, state: set[str], depth: int) -> list[str] | None:
        if depth > self.max_depth:
            return None
        if task in self.operators:
            return [task] if self.operators[task].applicable(state) else None
        applicable = [m for m in self.methods.get(task, []) if m.applicable(state)]
        if not applicable and task in self.cached_methods:
            return self._expand(self.cached_methods[task], state, depth)
        if not applicable:
            suggested = self.llm.decompose(task, set(state))
            if suggested is None:
                return None
            if not all(s in self.operators or s in self.methods for s in suggested):
                return None
            self.cached_methods[task] = tuple(suggested)
            return self._expand(tuple(suggested), state, depth)
        return self._expand(applicable[0].subtasks, state, depth)

    def _expand(self, subtasks: tuple[str, ...], state: set[str], depth: int) -> list[str] | None:
        """Plan the subtasks in turn, each from the state the ones before it leave behind."""
        plan: list[str] = []
        current = set(state)
        for subtask in subtasks:
            steps = self._plan(subtask, current, depth + 1)
            if steps is None:
                return None
            for step in steps:
                op = self.operators[step]
                if not op.applicable(current):
                    return None
                current = op.apply(current)
                plan.append(step)
        return plan
