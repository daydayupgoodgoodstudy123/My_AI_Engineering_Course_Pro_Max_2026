"""Contract chains: the project, feature, task and subtask contracts above one piece of work."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .contract import ScopeContract


@dataclass(frozen=True)
class Explanation:
    verdict: str  # "allowed", "forbidden" or "not_allowed"
    layer: str | None  # task_id of the contract that rules it out; None when allowed
    pattern: str | None  # the forbidden glob that matched; None otherwise


class ScopeChain:
    """The contracts that bound one piece of work, the project contract first."""

    def __init__(self, layers: list[ScopeContract]) -> None:
        self.layers = layers

    def effective(self) -> ScopeContract:
        """Every layer merged by least privilege, from the project down (merge_contracts)."""
        raise NotImplementedError

    def explain(self, path: str) -> Explanation:
        """Why a normalized repository path is or is not in scope.

        The path is forbidden when any layer's forbidden_files match it; the layer
        nearest the project explains it, with the first of its forbidden_files that
        matches. Otherwise the path is not allowed when any layer leaves it out of its
        allowed_files (or of a list in its allowed_within), and again the layer nearest
        the project explains it. A layer never widens the layers above it.
        """
        raise NotImplementedError

    def explain_host(self, host: str) -> Explanation:
        """Why a network host is or is not allowed.

        A layer whose network_egress is None does not restrict hosts; [] allows none.
        The layer nearest the project that leaves the host out explains it. Hosts compare
        the way scope_check compares them.
        """
        raise NotImplementedError


def resolve_chain(contracts: Iterable[ScopeContract], task_id: str) -> ScopeChain:
    """The chain of contracts from the project down to task_id.

    A contract's parent is the task_id of the contract one altitude up: a feature sits
    under the project, a task under a feature and a subtask under a task, and only the
    project contract has no parent. contracts may come in any order. An unknown task_id
    raises KeyError. Two contracts with the same task_id, a parent that is not there,
    and a parent at the wrong altitude (a layer skipped or out of order) raise ValueError.
    """
    raise NotImplementedError
