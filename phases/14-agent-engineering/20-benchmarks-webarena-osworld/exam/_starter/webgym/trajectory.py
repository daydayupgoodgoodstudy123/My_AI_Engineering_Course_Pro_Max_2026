"""Trajectory efficiency: agent actions against gold trajectories (the OSWorld-Human idea)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .harness import Action, Result

Op = tuple[str, Optional[int], Optional[int]]


def normalize(action: Action) -> tuple[str, tuple[tuple[str, Any], ...]]:
    """The comparable form of an action: skus are case-insensitive and add_to_cart's qty defaults to 1."""
    raise NotImplementedError


@dataclass(frozen=True)
class Alignment:
    ops: list[Op]

    def count(self, op: str) -> int:
        return sum(1 for name, _, _ in self.ops if name == op)


def align(agent: list[Action], gold: list[Action]) -> Alignment:
    """Align an agent's actions with a gold trajectory by edit distance.

    ops lists (op, agent_index, gold_index) in trajectory order:
      "match"       the same action once normalized, cost 0
      "substitute"  the same action name with other arguments (the right control, the
                    wrong target), cost 1
      "extra"       an agent action with no gold counterpart, gold_index None, cost 1
      "missing"     a gold action the agent never took, agent_index None, cost 1
    Actions with different names are never paired. The alignment has the lowest total cost.
    When several alignments tie, walk both trajectories from the start and take, at each
    point, the first of these that still leads to a lowest-cost alignment: pair the next two
    actions, skip the agent's next action, skip the next gold action.
    """
    raise NotImplementedError


def efficiency(results: list[Result]) -> dict[str, Optional[float]]:
    """Success rate and steps over gold for a run.

    Returns {"success_rate": float, "micro": float | None, "macro": float | None}.
    micro is total agent steps over total gold steps; macro is the mean of each task's
    steps / gold_steps. Both cover successful tasks only, since a failed task's step count
    says nothing about efficiency; with no successful task they are None.
    """
    raise NotImplementedError
