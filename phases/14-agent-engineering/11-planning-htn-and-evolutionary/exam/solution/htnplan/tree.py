"""Decomposition trees, and a check that replays one without trusting the planner."""
from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass

from .domain import Method, Operator

LLM = "llm"  # the method label of a decomposition that came from the LLM


@dataclass(frozen=True)
class Node:
    """One task in a decomposition tree.

    method names the library method that decomposed the task, or is "llm" when the decomposition
    came from the LLM (asked just now, or learned from it earlier). A primitive task, an operator,
    has method None and no children.
    """

    task: str
    method: str | None = None
    children: tuple[Node, ...] = ()


def leaves(node: Node) -> list[str]:
    """The operators under node, left to right: the plan the tree stands for."""
    if node.method is None and not node.children:
        return [node.task]
    return [step for child in node.children for step in leaves(child)]


def check(
    tree: Node,
    operators: dict[str, Operator],
    methods: dict[str, list[Method]],
    state: Set[str],
) -> tuple[int, ...] | None:
    """Replay a decomposition tree from state and return the path to the first node that breaks it.

    Nodes are checked in plan order: a task before its subtasks, subtasks left to right, with the
    state each operator leaves behind. An operator node has no method and no children, and its
    preconditions must hold. A node decomposed by a library method needs that method to exist for
    its task, the method's preconditions to hold, and children that are exactly the method's
    subtasks, in order. The children of an "llm" node must each name an operator or a library task.
    A path lists child indices from the root, so () is the root itself. Returns None when the whole
    tree replays. The state passed in is not changed.
    """
    current = frozenset(state)

    def visit(node: Node, path: tuple[int, ...]) -> tuple[int, ...] | None:
        nonlocal current
        if node.task in operators:
            op = operators[node.task]
            if node.method is not None or node.children or not op.applicable(current):
                return path
            current = frozenset(op.apply(current))
            return None
        if node.method == LLM:
            for i, child in enumerate(node.children):
                if child.task not in operators and child.task not in methods:
                    return path + (i,)
                broken = visit(child, path + (i,))
                if broken is not None:
                    return broken
            return None
        method = next((m for m in methods.get(node.task, []) if m.name == node.method), None)
        if (
            method is None
            or not method.applicable(current)
            or tuple(child.task for child in node.children) != method.subtasks
        ):
            return path
        for i, child in enumerate(node.children):
            broken = visit(child, path + (i,))
            if broken is not None:
                return broken
        return None

    return visit(tree, ())
