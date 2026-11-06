"""Learn RVQ codebooks: k-means++ seeding, Lloyd iterations, one stage at a time."""
from __future__ import annotations

import random

from .quantize import assign


def _sq_dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


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
    if not vectors:
        raise ValueError("cannot learn a codebook from no vectors")
    rng = random.Random(seed)
    codebook = [list(vectors[rng.randrange(len(vectors))])]
    d2 = [_sq_dist(v, codebook[0]) for v in vectors]
    while len(codebook) < size:
        total = sum(d2)
        if total == 0:
            codebook.append(list(codebook[0]))
            continue
        r = rng.random() * total
        running = 0.0
        pick = len(vectors) - 1
        for i, w in enumerate(d2):
            running += w
            if running > r:
                pick = i
                break
        codebook.append(list(vectors[pick]))
        d2 = [min(w, _sq_dist(v, codebook[-1])) for w, v in zip(d2, vectors)]

    for _ in range(iterations):
        labels = assign(vectors, codebook)
        sums = [[0.0] * len(vectors[0]) for _ in codebook]
        counts = [0] * len(codebook)
        for v, k in zip(vectors, labels):
            counts[k] += 1
            for j, x in enumerate(v):
                sums[k][j] += x
        moved = [
            [s / n for s in total] if n else old
            for total, n, old in zip(sums, counts, codebook)
        ]
        if moved == codebook:
            break
        codebook = moved
    return codebook


def train_rvq(
    frames: list[list[float]], n_stages: int, size: int, iterations: int = 20, seed: int = 0
) -> list[list[list[float]]]:
    """Train n_stages codebooks greedily, as in the lesson's rvq_encode.

    Stage q is learn_codebook(residual, size, iterations, seed + q), where residual is what
    stages 0..q-1 leave of the frames.
    """
    codebooks = []
    residual = [list(frame) for frame in frames]
    for q in range(n_stages):
        codebook = learn_codebook(residual, size, iterations, seed + q)
        codebooks.append(codebook)
        indices = assign(residual, codebook)
        residual = [[r - c for r, c in zip(res, codebook[i])] for res, i in zip(residual, indices)]
    return codebooks
