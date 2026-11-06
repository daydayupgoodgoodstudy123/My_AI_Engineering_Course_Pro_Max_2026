"""Glue used by the API layer: generate, store, score and stream."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .compose import PPQ, compose, render
from .fad import embed, frechet_distance
from .store import Track, TrackStore
from .stream import stream_bars


class MusicBox:
    def __init__(self, store: TrackStore, model: str = "musicbox-toy") -> None:
        self.store = store
        self.model = model

    def generate(self, prompt: str, bars: int = 8, seed: int = 0) -> str:
        """Compose and render a prompt, and store the track with its generation record."""
        piece = compose(prompt, bars)
        track = Track(
            title=prompt,
            ppq=PPQ,
            tempo=[(0, float(piece.bpm))],
            notes=render(piece),
            meta={"model": self.model, "prompt": prompt, "seed": seed, "ai_generated": True},
        )
        return self.store.add(track)

    def fad(self, reference: list[str], prompts: list[str]) -> float:
        """FAD of the pieces generated for prompts, against the pieces for the reference prompts."""
        return frechet_distance(
            [embed(compose(p)) for p in reference], [embed(compose(p)) for p in prompts]
        )

    def stream(self, tokens: AsyncIterator[str]) -> AsyncIterator[str]:
        """Live playback feed for the player; stream_bars defines the wire format."""
        return stream_bars(tokens)
