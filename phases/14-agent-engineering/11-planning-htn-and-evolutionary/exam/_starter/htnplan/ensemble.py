"""The evolve() search with an ensemble of async mutators, reported one CSV line per generation."""
from __future__ import annotations

import random
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

from .evolve import Genome

AsyncMutator = Callable[[Genome, random.Random], Awaitable[Genome]]


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
    raise NotImplementedError
