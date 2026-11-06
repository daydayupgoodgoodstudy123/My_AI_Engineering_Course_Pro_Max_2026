"""ToT with an LLM judge under a token budget, streamed as NDJSON while the judgements come back."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from .game import State, Step, children, solved, start

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
    used = 0
    frontier: list[tuple[State, list[Step]]] = [(start(numbers), [])]
    if solved(frontier[0][0]):
        yield _line({"stop": "solved", "tokens_used": 0, "trace": []})
        return
    depth = 0
    while frontier:
        depth += 1
        found: dict[State, list[Step]] = {}
        for state, trace in frontier:
            for step, child in children(state):
                if child not in found:
                    found[child] = trace + [step]
        order = list(found)

        async def judged(i: int) -> tuple[int, float, int]:
            value, tokens = await judge(order[i])
            return i, value, tokens

        tasks = [asyncio.create_task(judged(i)) for i in range(len(order))]
        values = [0.0] * len(order)
        try:
            for next_back in asyncio.as_completed(tasks):
                i, value, tokens = await next_back
                used += tokens
                values[i] = value
                yield _line({"depth": depth, "state": [str(x) for x in order[i]], "value": value, "tokens_used": used})
                if solved(order[i]):
                    trace = [str(step) for step in found[order[i]]]
                    yield _line({"stop": "solved", "tokens_used": used, "trace": trace})
                    return
                if used >= budget:
                    yield _line({"stop": "budget", "tokens_used": used})
                    return
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        best = sorted(range(len(order)), key=lambda i: -values[i])[:beam]
        frontier = [(order[i], found[order[i]]) for i in best]
    yield _line({"stop": "exhausted", "tokens_used": used})


def _line(record: dict) -> str:
    return json.dumps(record) + "\n"
