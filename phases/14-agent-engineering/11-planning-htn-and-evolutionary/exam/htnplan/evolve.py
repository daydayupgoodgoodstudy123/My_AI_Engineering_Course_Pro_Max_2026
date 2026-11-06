"""AlphaEvolve-style search: an ensemble of mutators proposes, a deterministic evaluator selects."""
from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

Genome = list[int]
Mutator = Callable[[Genome, random.Random], Genome]


@dataclass(frozen=True)
class Generation:
    number: int  # 0 is the seed genome on its own
    best: Genome
    fitness: float  # lower is better
    evaluations: int  # evaluator calls so far
    cache_hits: int  # children scored from the cache so far


def evolve(
    seed_genome: Genome,
    evaluate: Callable[[Genome], float],
    mutators: Sequence[Mutator],
    *,
    seed: int,
    generations: int,
    survivors: int = 3,
    budget: int | None = None,
    target: float | None = None,
) -> list[Generation]:
    """Evolve seed_genome and return one Generation per generation, starting with generation 0.

    Generation 0 is the seed genome alone. In each later generation the parents are taken best
    first, and each one is handed to every mutator, in ensemble order, before the next parent.
    Mutator m working on parent p (0 is the best) in generation g draws only from
    random.Random(f"{seed}/{g}/{p}/{m}"), and gets its own copy of the parent. The parents of the
    next generation are the `survivors` best distinct genomes among the parents and their
    children, ranked by (fitness, genome).

    The evaluator runs at most once per distinct genome in a run; a genome seen before is scored
    from the cache. The run ends with generation number `generations`, or with the first
    generation whose best fitness is at most target. It also ends as soon as the evaluator has
    been called `budget` times: nothing more is mutated or scored, and the generation in progress
    ends with the children it has. That last generation is reported like any other.
    """
    raise NotImplementedError
