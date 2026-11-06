"""Glue used by the API layer: quick ToT answers, resumable LATS searches, streamed judging."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .checkpoint import load, save
from .expr import build, render
from .game import Step
from .mcts import run
from .stream import Judge, stream_tot
from .tot import tot_bfs
from .tree import Search


class Solver:
    def __init__(self, beam: int = 5, c: float = 1.4) -> None:
        self.beam = beam
        self.c = c

    def answer(self, numbers: list[int]) -> str | None:
        """Solve a deal with ToT and write the solution as an expression."""
        trace = tot_bfs(numbers, self.beam)
        return None if trace is None else explain(numbers, trace)

    def start(self, numbers: list[int], seed: int) -> bytes:
        """A fresh LATS search for a deal, as a checkpoint."""
        return save(Search.new(numbers, seed, self.c))

    def resume(self, checkpoint: bytes, iterations: int) -> tuple[bytes, str | None]:
        """Run a checkpointed search a little further; return the new checkpoint and the answer, if any."""
        search = load(checkpoint)
        trace = run(search, iterations)
        numbers = list(search.root.state)
        return save(search), None if trace is None else explain(numbers, trace)

    def stream(self, numbers: list[int], judge: Judge, budget: int) -> AsyncIterator[str]:
        """ToT with an LLM judge; stream_tot defines the wire format."""
        return stream_tot(numbers, judge, budget, self.beam)


def explain(numbers: list[int], trace: list[Step]) -> str:
    """A solution's steps as one expression, e.g. "5 * (5 - 1 / 5)"."""
    return render(build(numbers, trace))
