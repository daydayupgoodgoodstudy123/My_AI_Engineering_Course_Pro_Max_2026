"""Fréchet Audio Distance on 2-D embeddings, and a toy embedding for symbolic pieces."""
from __future__ import annotations

import math

from .compose import BAR, DRUM_CHANNEL, Piece, render, seconds

Embedding = tuple[float, float]
Matrix = tuple[tuple[float, float], tuple[float, float]]


def embed(piece: Piece) -> Embedding:
    """A toy stand-in for a VGGish embedding: mean chord-tone pitch, and drum hits per second."""
    notes = render(piece)
    tones = [note.pitch for note in notes if note.channel != DRUM_CHANNEL]
    hits = sum(note.channel == DRUM_CHANNEL for note in notes)
    return (sum(tones) / len(tones), hits / seconds(piece, len(piece.chords) * BAR))


def frechet_distance(real: list[Embedding], generated: list[Embedding]) -> float:
    """Fréchet distance between Gaussians fitted to two sets of 2-D embeddings.

    FAD = |mu_r - mu_g|^2 + tr(S_r) + tr(S_g) - 2 tr(sqrt(S_r S_g)), where mu is the mean and S
    the sample covariance (divide by n - 1), as the frechet_audio_distance package computes it.
    Each set needs at least two embeddings. A distance is never negative.
    """
    mu_r, s_r = _gaussian(real)
    mu_g, s_g = _gaussian(generated)
    (m00, m01), (m10, m11) = _matmul(s_r, s_g)
    # The eigenvalues of S_r S_g are real and non-negative, so for a 2x2 product
    # tr sqrt(M) = sqrt(l1) + sqrt(l2) = sqrt(tr M + 2 sqrt(det M)).
    det = max(0.0, m00 * m11 - m01 * m10)
    tr_sqrt = math.sqrt(max(0.0, m00 + m11 + 2.0 * math.sqrt(det)))
    mean_term = (mu_r[0] - mu_g[0]) ** 2 + (mu_r[1] - mu_g[1]) ** 2
    distance = mean_term + s_r[0][0] + s_r[1][1] + s_g[0][0] + s_g[1][1] - 2.0 * tr_sqrt
    return max(0.0, distance)


def rank_models(reference: list[Embedding], generated: dict[str, list[Embedding]]) -> list[tuple[str, float]]:
    """(model, FAD against the reference) for every model, best model first."""
    scores = [(name, frechet_distance(reference, embeddings)) for name, embeddings in generated.items()]
    return sorted(scores, key=lambda item: item[1])


def _gaussian(points: list[Embedding]) -> tuple[Embedding, Matrix]:
    n = len(points)
    if n < 2:
        raise ValueError("need at least two embeddings to estimate a covariance")
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points) / (n - 1)
    syy = sum((y - my) ** 2 for _, y in points) / (n - 1)
    sxy = sum((x - mx) * (y - my) for x, y in points) / (n - 1)
    return (mx, my), ((sxx, sxy), (sxy, syy))


def _matmul(a: Matrix, b: Matrix) -> Matrix:
    return (
        (a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]),
        (a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]),
    )
