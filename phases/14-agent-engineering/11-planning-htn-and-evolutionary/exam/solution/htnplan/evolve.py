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


def mutation_rng(seed: int, generation: int, parent: int, mutator: int) -> random.Random:
    """The generator one mutation draws from, fixed by where the mutation sits in the run."""
    return random.Random(f"{seed}/{generation}/{parent}/{mutator}")


class Pool:
    """What a search keeps between generations: the parents, the fitness cache and the counters."""

    def __init__(self, survivors: int, budget: int | None, target: float | None) -> None:
        if survivors < 1:
            raise ValueError("survivors must be at least 1")
        if budget is not None and budget < 1:
            raise ValueError("budget must be at least 1")
        self.survivors = survivors
        self.budget = budget
        self.target = target
        self.fitness: dict[tuple[int, ...], float] = {}
        self.parents: list[tuple[int, ...]] = []
        self.evaluations = 0
        self.cache_hits = 0
        self.finished = False

    def spent(self) -> bool:
        return self.budget is not None and self.evaluations >= self.budget

    def scored(self, genome: tuple[int, ...]) -> bool:
        """True, counting a cache hit, if genome has been evaluated before."""
        if genome in self.fitness:
            self.cache_hits += 1
            return True
        return False

    def record(self, genome: tuple[int, ...], fitness: float) -> None:
        self.fitness[genome] = fitness
        self.evaluations += 1

    def close(self, number: int, children: list[tuple[int, ...]]) -> Generation:
        """End a generation: keep the best distinct genomes, ranked by (fitness, genome)."""
        ranked = sorted(set(self.parents) | set(children), key=lambda g: (self.fitness[g], g))
        self.parents = ranked[: self.survivors]
        best = self.parents[0]
        fitness = self.fitness[best]
        if self.spent() or (self.target is not None and fitness <= self.target):
            self.finished = True
        return Generation(number, list(best), fitness, self.evaluations, self.cache_hits)


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
    pool = Pool(survivors, budget, target)
    first = tuple(seed_genome)
    pool.record(first, evaluate(list(first)))
    history = [pool.close(0, [first])]
    for g in range(1, generations + 1):
        if pool.finished:
            break
        children: list[tuple[int, ...]] = []
        for p, parent in enumerate(pool.parents):
            for m, mutate in enumerate(mutators):
                if pool.spent():
                    break
                child = tuple(mutate(list(parent), mutation_rng(seed, g, p, m)))
                if not pool.scored(child):
                    pool.record(child, evaluate(list(child)))
                children.append(child)
        history.append(pool.close(g, children))
    return history
