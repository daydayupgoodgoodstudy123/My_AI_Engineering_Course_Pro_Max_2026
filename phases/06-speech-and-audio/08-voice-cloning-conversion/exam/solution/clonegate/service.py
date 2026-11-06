"""Consent-gated voice conversion: the glue the API layer calls."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from .consent import Consent, ConsentRegistry
from .knnvc import knn_convert
from .monitor import watch
from .watermark import Watermarker, bits_to_int, int_to_bits


@dataclass(frozen=True)
class Conversion:
    frames: list[list[float]]
    consent_id: int


class CloneGate:
    """Every conversion is built from consented target audio and stamped with its consent id."""

    def __init__(self, registry: ConsentRegistry, watermarker: Watermarker, k: int = 4) -> None:
        self.registry = registry
        self.watermarker = watermarker
        self.k = k
        self._frames: list[tuple[int, str, list[float]]] = []  # (consent_id, speaker, frame)

    def enroll(self, consent_id: int, frames: list[list[float]]) -> None:
        """Store target-speaker frames recorded under a consent. Unknown consents raise KeyError."""
        speaker = self.registry.get(consent_id).speaker
        self._frames.extend((consent_id, speaker, list(frame)) for frame in frames)

    def convert(self, source: list[list[float]], consent_id: int, purpose: str, at: datetime) -> Conversion:
        """Convert source frames into the voice of the consent's speaker with kNN-VC (k = self.k).

        The consent must allow purpose at time at, or PermissionError. The matching set is the
        frames enrolled under this consent, in enrollment order, and nothing else.
        """
        consent = self.registry.get(consent_id)
        if not consent.allows(purpose, at):
            raise PermissionError(f"consent {consent_id} does not allow {purpose!r} at {at.isoformat()}")
        matching = [frame for owner, _, frame in self._frames if owner == consent_id]
        return Conversion(knn_convert(source, matching, self.k), consent_id)

    def stamp(self, audio: list[float], consent_id: int) -> list[float]:
        """Watermark rendered audio with the id of the consent that authorized it."""
        return self.watermarker.embed(audio, int_to_bits(consent_id, self.watermarker.n_bits))

    def trace(self, audio: list[float]) -> Consent | None:
        """The consent a clip was stamped with, or None when it carries no mark."""
        detection = self.watermarker.detect(audio)
        if not detection.found:
            return None
        return self.registry.get(bits_to_int(detection.bits))

    def watch(self, chunks: AsyncIterator[list[float]], sample_rate: int) -> AsyncIterator[str]:
        """Watch a live stream for the mark; monitor.watch defines the wire format."""
        return watch(chunks, self.watermarker, sample_rate)
