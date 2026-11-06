"""LATS-style Monte Carlo Tree Search: select with UCT, expand, roll out, backpropagate."""
from __future__ import annotations

import math
import random

from .game import Step, children, reward, solved
from .tree import Node, Search


def uct(parent: Node, child: Node, c: float) -> float:
    """Q(s, a) + c * sqrt(ln N(s) / N(s, a)). A child that was never visited scores +inf."""
    if child.visits == 0:
        return math.inf
    return child.q + c * math.sqrt(math.log(parent.visits) / child.visits)


def iterate(search: Search) -> list[Step] | None:
    """Run one MCTS iteration; return the solution if this iteration found one.

    1. Select: from the root, while the node has children, step to the child with the highest
       uct() score; ties go to the earlier child.
    2. Expand: if the leaf reached has been visited before and is not finished (it holds more
       than one number), it gets all of children() as nodes, in order, and the iteration steps
       to the first of them. A finished node is never expanded.
    3. Simulate: from the node reached, pick rng.choice(children(state)) until one number is
       left, with rng = random.Random(f"{search.seed}:{i}"), where i is the number of
       iterations the search had run before this one. The reward is game.reward() of the
       finished state.
    4. Backpropagate: every node from the root down to the node the rollout started from gets
       one more visit and the reward added to its value_sum.
    The iteration has found a solution when the finished state is 24; the solution is the trace
    of the node the rollout started from, followed by the rollout's steps.
    search.iterations counts every iteration.
    """
    rng = random.Random(f"{search.seed}:{search.iterations}")
    node = search.root
    path = [node]
    while node.children:
        parent = node
        node = max(parent.children, key=lambda child: uct(parent, child, search.c))
        path.append(node)
    if node.visits > 0 and len(node.state) > 1:
        node.children = [Node(state, node.trace + [step]) for step, state in children(node.state)]
        node = node.children[0]
        path.append(node)
    state, rollout = node.state, []
    while len(state) > 1:
        step, state = rng.choice(children(state))
        rollout.append(step)
    score = reward(state)
    for visited in path:
        visited.visits += 1
        visited.value_sum += score
    search.iterations += 1
    return node.trace + rollout if solved(state) else None


def run(search: Search, iterations: int) -> list[Step] | None:
    """Run up to `iterations` more iterations, stopping at the first solution.

    Returns search.solution, which stays None until an iteration finds a solution. A search
    that already has a solution runs no more iterations.
    """
    for _ in range(iterations):
        if search.solution is not None:
            break
        search.solution = iterate(search)
    return search.solution
