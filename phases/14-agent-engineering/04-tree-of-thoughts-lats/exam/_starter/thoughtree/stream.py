"""ToT with an LLM judge under a token budget, streamed as NDJSON while the judgements come back."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from .game import State

# judge(state) -> (value, tokens the call cost)
Judge = Callable[[State], Awaitable[tuple[float, int]]]


async def stream_tot(numbers: list[int], judge: Judge, budget: int, beam: int = 5) -> AsyncIterator[str]:
    """Run ToT with an LLM judge and stream one NDJSON line per judgement.

    The search goes level by level like tot_bfs: the distinct children of the frontier, in the
    order they are found, are all sent to the judge at once, solved children included (the
    judge's reply is what confirms an answer). Each judgement that comes back yields a line
    right away, in the order they come back:
        {"depth": 1, "state": ["10", "1/5"], "value": 0.5, "tokens_used": 120}
    depth counts the steps from the deal, numbers are written as strings, and tokens_used is
    the total cost of the judgements that have come back, this one included.
    Once a level is fully judged, the next frontier is its beam best states by the judge's
    values, highest first, ties in the order they were found.

    The stream ends with one stop line:
        {"stop": "solved", "tokens_used": ..., "trace": ["6 * 4 = 24"]}  right after the line
            of a solved state;
        {"stop": "budget", "tokens_used": ...}  right after the line that brings tokens_used
            to the budget or past it (a solved state wins over the budget);
        {"stop": "exhausted", "tokens_used": ...}  when there is nothing left to judge.
    A deal that is already 24 needs no judgement: its stream is just the solved line, with an
    empty trace. Stopping cancels the judgements still running and waits for them to finish
    cancelling; nothing comes after the stop line.
    """
    raise NotImplementedError
