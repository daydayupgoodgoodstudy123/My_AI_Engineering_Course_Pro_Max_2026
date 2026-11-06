"""The LATS search tree: nodes with MCTS statistics, and the search that owns them."""
from __future__ import annotations

from dataclasses import dataclass, field

from .game import State, Step, start


@dataclass
class Node:
    state: State
    trace: list[Step]  # the steps from the root to this node
    visits: int = 0
    value_sum: float = 0.0
    children: list[Node] = field(default_factory=list)

    @property
    def q(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass
class Search:
    """One MCTS run over a deal, in a form that can be checkpointed and resumed."""

    root: Node
    seed: int
    c: float = 1.4
    iterations: int = 0  # iterations run so far, over every resume
    solution: list[Step] | None = None  # the first solution found; [] when the deal is just 24

    @classmethod
    def new(cls, numbers: list[int], seed: int, c: float = 1.4) -> Search:
        return cls(Node(start(numbers), []), seed, c)
