"""Glue used by the API layer: decode, store, stream and rescore."""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from .ctc import Frame, transcribe
from .lattice import Arc, best_path
from .store import TranscriptStore
from .stream import stream_words


class ASRService:
    def __init__(self, store: TranscriptStore, frame_ms: int = 20) -> None:
        self.store = store
        self.frame_ms = frame_ms

    def record(
        self, utt_id: str, model: str, frames: Sequence[Frame], beam: int | None = None
    ) -> str:
        """Decode one utterance and store the transcript as the given model's hypothesis."""
        text = transcribe(frames, beam)
        self.store.add_hypothesis(utt_id, model, text)
        return text

    def stream(self, chunks: AsyncIterator[Sequence[Frame]]) -> AsyncIterator[str]:
        """Decode a live stream; stream_words defines the wire format."""
        return stream_words(chunks, self.frame_ms)

    def rescore(self, arcs: list[Arc], start: int, end: int, lm_weight: float = 1.0) -> str:
        """The best transcript through a lattice from a first decoding pass."""
        return best_path(arcs, start, end, lm_weight)[0]
