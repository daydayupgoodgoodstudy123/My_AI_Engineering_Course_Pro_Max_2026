"""Fréchet Audio Distance on 2-D embeddings, and a toy embedding for symbolic pieces."""
from __future__ import annotations

from .compose import BAR, DRUM_CHANNEL, Piece, render, seconds

Embedding = tuple[float, float]


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
    raise NotImplementedError


def rank_models(reference: list[Embedding], generated: dict[str, list[Embedding]]) -> list[tuple[str, float]]:
    """(model, FAD against the reference) for every model, best model first."""
    raise NotImplementedError
