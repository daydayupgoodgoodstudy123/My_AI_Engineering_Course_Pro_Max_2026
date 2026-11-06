"""Tree of Thoughts as a level-by-level beam search."""
from __future__ import annotations

from .game import Step, State, children, solved, start, value


def tot_bfs(numbers: list[int], beam: int | None = 5) -> list[Step] | None:
    """Search a deal level by level; return the steps of a solution, or None if there is none.

    Every level expands the states of the frontier in order. A child that is solved ends the
    search at once, without asking the judge. Every other child gets a score from value(), and
    the next frontier is the beam best children, highest score first, ties in the order they
    were found. beam=None keeps every child, which makes this a plain BFS.
    A state that several paths reach within one level is scored and kept once, through the
    first path that reached it.
    """
    frontier: list[tuple[State, list[Step]]] = [(start(numbers), [])]
    if solved(frontier[0][0]):
        return []
    while frontier:
        scored: list[tuple[float, State, list[Step]]] = []
        for state, trace in frontier:
            for step, child in children(state):
                score = value(child)
                if score > 0.99:
                    return trace + [step]
                scored.append((score, child, trace + [step]))
        scored.sort(key=lambda item: item[0], reverse=True)
        frontier = [(child, trace) for _, child, trace in scored[:beam]]
    return None
