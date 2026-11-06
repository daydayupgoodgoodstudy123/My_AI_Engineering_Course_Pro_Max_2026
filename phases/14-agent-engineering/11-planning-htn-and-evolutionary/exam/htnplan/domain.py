"""HTN building blocks: operators (primitive actions) and methods (ways to decompose a task)."""
from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass


@dataclass(frozen=True)
class Operator:
    """A primitive action. It runs when every precondition holds, then removes and adds facts."""

    name: str
    preconditions: tuple[str, ...]
    effects_add: tuple[str, ...]
    effects_remove: tuple[str, ...] = ()

    def applicable(self, state: Set[str]) -> bool:
        return all(p in state for p in self.preconditions)

    def apply(self, state: Set[str]) -> set[str]:
        """The state after this operator runs. The state passed in is not changed."""
        new_state = set(state)
        new_state.difference_update(self.effects_remove)
        new_state.update(self.effects_add)
        return new_state


@dataclass(frozen=True)
class Method:
    """One way to decompose a compound task into subtasks, usable while its preconditions hold."""

    name: str
    task: str
    preconditions: tuple[str, ...]
    subtasks: tuple[str, ...]

    def applicable(self, state: Set[str]) -> bool:
        return all(p in state for p in self.preconditions)
