"""Task classes as a tree, and which reflections a task class gets to see.

A task class is a path: math/arith/sum sits under math/arith, which sits under math. A
reflection attached to a class applies to that class and to everything below it, never to its
siblings or to the classes above it. Reflexion only helps when the task class is reproducible;
the tree says how far each lesson reaches.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .memory import TASK_CLASS_PATH, Reflection


@dataclass(frozen=True)
class Recalled:
    """A reflection recalled for a task class. scope is the class it is attached to."""

    scope: str
    reflection: Reflection
    suspicious: bool


class ScopeTree:
    """Every declared class and every prefix of one is a class: declaring math/arith/sum declares
    math/arith and math too. A declared class must be a task-class path (ValueError)."""

    def __init__(self, classes: Iterable[str]) -> None:
        self._attached: dict[str, list[Reflection]] = {}
        for task_class in classes:
            if not TASK_CLASS_PATH.fullmatch(task_class):
                raise ValueError(f"not a task class: {task_class!r}")
            parts = task_class.split("/")
            for depth in range(1, len(parts) + 1):
                self._attached.setdefault("/".join(parts[:depth]), [])

    def attach(self, reflection: Reflection) -> None:
        """Attach a reflection to its task_class. An unknown class raises KeyError."""
        self._known(reflection.task_class).append(reflection)

    def recall(self, task_class: str, per_level: int = 2, total: int = 6) -> list[Recalled]:
        """The reflections a trial of task_class sees: the class's own, then its parent's, and so
        on up to its root class.

        Nearest level first. Within a level, the most recent trial first, and reflections with
        the same trial in the order they were attached. At most per_level reflections come from
        each level, and at most total in all.

        A reflection attached to a root class (a class with no parent) that came from a single
        failure is suspicious: one failure became a rule for a whole family of tasks, which is
        how a reflection turns into superstition. It is still recalled, marked.

        An unknown task class raises KeyError.
        """
        self._known(task_class)
        recalled: list[Recalled] = []
        parts = task_class.split("/")
        for depth in range(len(parts), 0, -1):
            scope = "/".join(parts[:depth])
            level = sorted(self._attached[scope], key=lambda r: -r.trial)
            for reflection in level[:per_level]:
                if len(recalled) == total:
                    return recalled
                recalled.append(Recalled(scope, reflection, depth == 1 and reflection.failures == 1))
        return recalled

    def _known(self, task_class: str) -> list[Reflection]:
        if task_class not in self._attached:
            raise KeyError(f"unknown task class: {task_class!r}")
        return self._attached[task_class]
