"""Glue used by the API layer: featurize, store, tag and stream."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .bank import ClipBank
from .classify import classify
from .features import featurize, summarize
from .stream import stream_labels


class TaggingService:
    def __init__(self, bank: ClipBank, sample_rate: int, k: int = 3) -> None:
        self.bank = bank
        self.sample_rate = sample_rate
        self.k = k

    def register(self, label: str, split: str, signal: list[float]) -> str:
        """Featurize a labeled clip and store it."""
        features = summarize(featurize(signal, self.sample_rate))
        return self.bank.add(label, split, self.sample_rate, features)

    def tag(self, signal: list[float]) -> str:
        """Label one clip."""
        return classify(self.bank, summarize(featurize(signal, self.sample_rate)), self.k)

    def stream(self, chunks: AsyncIterator[list[float]]) -> AsyncIterator[str]:
        """Label a live stream; stream_labels defines the wire format."""
        return stream_labels(chunks, self.sample_rate, self.tag)
