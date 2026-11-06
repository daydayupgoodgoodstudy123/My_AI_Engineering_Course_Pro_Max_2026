"""The evolve() search with an ensemble of async mutators, reported one CSV line per generation."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

from .evolve import Generation, Genome, Pool, mutation_rng

AsyncMutator = Callable[[Genome, random.Random], Awaitable[Genome]]
COLUMNS = ("gen", "best_genome", "best_fitness", "evaluations", "cache_hits")


async def stream_generations(
    seed_genome: Genome,
    evaluate: Callable[[Genome], Awaitable[float]],
    mutators: Sequence[AsyncMutator],
    *,
    seed: int,
    generations: int,
    survivors: int = 3,
    budget: int | None = None,
    target: float | None = None,
) -> AsyncIterator[str]:
    """Run evolve()'s search with async mutators, yielding a CSV header and then a line per generation.

    The columns are gen,best_genome,best_fitness,evaluations,cache_hits: best_genome as a JSON
    list, the numbers as str() writes them. A generation's line is yielded as soon as the
    generation ends, before the next one starts. All mutations of a generation start at once.
    The evaluator, the bottleneck, scores one child at a time, each as soon as it and every
    child before it in evolve()'s order (parent rank, then mutator) are ready, so every line
    matches evolve()'s Generation whichever mutator answers first. Mutations still running
    when the budget runs out are cancelled before the last line.
    """
    pool = Pool(survivors, budget, target)
    yield _line(COLUMNS)
    first = tuple(seed_genome)
    pool.record(first, await evaluate(list(first)))
    yield _row(pool.close(0, [first]))
    for g in range(1, generations + 1):
        if pool.finished:
            break
        tasks = [
            asyncio.ensure_future(mutate(list(parent), mutation_rng(seed, g, p, m)))
            for p, parent in enumerate(pool.parents)
            for m, mutate in enumerate(mutators)
        ]
        children: list[tuple[int, ...]] = []
        try:
            for task in tasks:
                if pool.spent():
                    break
                child = tuple(await task)
                if not pool.scored(child):
                    pool.record(child, await evaluate(list(child)))
                children.append(child)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        yield _row(pool.close(g, children))


def _row(gen: Generation) -> str:
    return _line((gen.number, json.dumps(gen.best), gen.fitness, gen.evaluations, gen.cache_hits))


def _line(values) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(values)
    return out.getvalue()
