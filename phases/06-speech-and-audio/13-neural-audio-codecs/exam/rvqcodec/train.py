"""Learn RVQ codebooks: k-means++ seeding, Lloyd iterations, one stage at a time."""
from __future__ import annotations

import random

from .quantize import assign


def learn_codebook(
    vectors: list[list[float]], size: int, iterations: int = 20, seed: int = 0
) -> list[list[float]]:
    """A k-means codebook of size codewords, the same for the same seed.

    Seeding is k-means++ with rng = random.Random(seed). The first codeword is
    vectors[rng.randrange(len(vectors))]. Every next codeword is vectors[i] for the first i
    whose running total of D(x)^2 exceeds rng.random() * (the sum of all D(x)^2), where
    D(x) is the distance from x to its nearest codeword so far. Once every vector sits on a
    codeword, the remaining codewords are copies of the first one.

    Then up to `iterations` rounds of Lloyd: assign every vector to its nearest codeword
    (ties go to the lower index) and move every codeword to the mean of its vectors. A
    codeword that gets no vectors stays where it is. Codewords keep their seeding order.
    """
    raise NotImplementedError


def train_rvq(
    frames: list[list[float]], n_stages: int, size: int, iterations: int = 20, seed: int = 0
) -> list[list[list[float]]]:
    """Train n_stages codebooks greedily, as in the lesson's rvq_encode.

    Stage q is learn_codebook(residual, size, iterations, seed + q), where residual is what
    stages 0..q-1 leave of the frames.
    """
    raise NotImplementedError
