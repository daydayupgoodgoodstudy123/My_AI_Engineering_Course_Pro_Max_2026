"""Contract chains: the project, feature, task and subtask contracts above one piece of work."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .check import normalize_host
from .contract import ALTITUDES, ScopeContract, merge_contracts
from .patterns import PatternSet


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
        merged = self.layers[0]
        for layer in self.layers[1:]:
            merged = merge_contracts(merged, layer)
        return merged

    def explain(self, path: str) -> Explanation:
        """Why a normalized repository path is or is not in scope.

        The path is forbidden when any layer's forbidden_files match it; the layer
        nearest the project explains it, with the first of its forbidden_files that
        matches. Otherwise the path is not allowed when any layer leaves it out of its
        allowed_files (or of a list in its allowed_within), and again the layer nearest
        the project explains it. A layer never widens the layers above it.
        """
        for layer in self.layers:
            for pattern in layer.forbidden_files:
                if PatternSet([pattern]).matches(path):
                    return Explanation("forbidden", layer.task_id, pattern)
        for layer in self.layers:
            for allowed in (layer.allowed_files, *layer.allowed_within):
                if not PatternSet(allowed).matches(path):
                    return Explanation("not_allowed", layer.task_id, None)
        return Explanation("allowed", None, None)

    def explain_host(self, host: str) -> Explanation:
        """Why a network host is or is not allowed.

        A layer whose network_egress is None does not restrict hosts; [] allows none.
        The layer nearest the project that leaves the host out explains it. Hosts compare
        the way scope_check compares them.
        """
        host = normalize_host(host)
        for layer in self.layers:
            if layer.network_egress is None:
                continue
            if host not in {normalize_host(h) for h in layer.network_egress}:
                return Explanation("not_allowed", layer.task_id, None)
        return Explanation("allowed", None, None)


def resolve_chain(contracts: Iterable[ScopeContract], task_id: str) -> ScopeChain:
    """The chain of contracts from the project down to task_id.

    A contract's parent is the task_id of the contract one altitude up: a feature sits
    under the project, a task under a feature and a subtask under a task, and only the
    project contract has no parent. contracts may come in any order. An unknown task_id
    raises KeyError. Two contracts with the same task_id, a parent that is not there,
    and a parent at the wrong altitude (a layer skipped or out of order) raise ValueError.
    """
    by_id: dict[str, ScopeContract] = {}
    for contract in contracts:
        if contract.task_id in by_id:
            raise ValueError(f"two contracts are called {contract.task_id!r}")
        by_id[contract.task_id] = contract
    if task_id not in by_id:
        raise KeyError(task_id)
    chain: list[ScopeContract] = []
    current = by_id[task_id]
    while True:
        if current.altitude not in ALTITUDES:
            raise ValueError(f"{current.task_id}: unknown altitude {current.altitude!r}")
        chain.append(current)
        level = ALTITUDES.index(current.altitude)
        if level == 0:
            if current.parent is not None:
                raise ValueError(f"the project contract {current.task_id} has a parent")
            break
        if current.parent is None:
            raise ValueError(f"{current.task_id} ({current.altitude}) has no parent")
        parent = by_id.get(current.parent)
        if parent is None:
            raise ValueError(f"{current.task_id}: parent {current.parent!r} is missing")
        if parent.altitude != ALTITUDES[level - 1]:
            raise ValueError(
                f"{current.task_id} ({current.altitude}) sits under {parent.task_id} ({parent.altitude})"
            )
        current = parent
    chain.reverse()
    return ScopeChain(chain)
