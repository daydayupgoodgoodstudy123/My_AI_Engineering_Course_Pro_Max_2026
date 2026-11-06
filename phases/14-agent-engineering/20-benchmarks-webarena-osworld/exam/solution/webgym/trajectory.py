"""Trajectory efficiency: agent actions against gold trajectories (the OSWorld-Human idea)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .harness import Action, Result

Op = tuple[str, Optional[int], Optional[int]]


def normalize(action: Action) -> tuple[str, tuple[tuple[str, Any], ...]]:
    """The comparable form of an action: skus are case-insensitive and add_to_cart's qty defaults to 1."""
    args = dict(action.args)
    if isinstance(args.get("sku"), str):
        args["sku"] = args["sku"].lower()
    if action.name == "add_to_cart":
        args.setdefault("qty", 1)
    return action.name, tuple(sorted(args.items()))


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
    a = [normalize(x) for x in agent]
    g = [normalize(x) for x in gold]
    n, m = len(a), len(g)

    def pair_cost(i: int, j: int) -> Optional[int]:
        if a[i] == g[j]:
            return 0
        if a[i][0] == g[j][0]:
            return 1
        return None

    # rest[i][j]: cheapest alignment of a[i:] with g[j:]
    rest = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n or j == m:
                rest[i][j] = (n - i) + (m - j)
                continue
            best = 1 + min(rest[i + 1][j], rest[i][j + 1])
            cost = pair_cost(i, j)
            if cost is not None:
                best = min(best, cost + rest[i + 1][j + 1])
            rest[i][j] = best

    ops: list[Op] = []
    i = j = 0
    while i < n or j < m:
        cost = pair_cost(i, j) if i < n and j < m else None
        if cost is not None and cost + rest[i + 1][j + 1] == rest[i][j]:
            ops.append(("match" if cost == 0 else "substitute", i, j))
            i, j = i + 1, j + 1
        elif i < n and 1 + rest[i + 1][j] == rest[i][j]:
            ops.append(("extra", i, None))
            i += 1
        else:
            ops.append(("missing", None, j))
            j += 1
    return Alignment(ops)


def efficiency(results: list[Result]) -> dict[str, Optional[float]]:
    """Success rate and steps over gold for a run.

    Returns {"success_rate": float, "micro": float | None, "macro": float | None}.
    micro is total agent steps over total gold steps; macro is the mean of each task's
    steps / gold_steps. Both cover successful tasks only, since a failed task's step count
    says nothing about efficiency; with no successful task they are None.
    """
    if not results:
        raise ValueError("no results")
    solved = [r for r in results if r.success]
    report: dict[str, Optional[float]] = {
        "success_rate": len(solved) / len(results),
        "micro": None,
        "macro": None,
    }
    if solved:
        report["micro"] = sum(r.steps for r in solved) / sum(r.gold_steps for r in solved)
        report["macro"] = sum(r.steps / r.gold_steps for r in solved) / len(solved)
    return report
