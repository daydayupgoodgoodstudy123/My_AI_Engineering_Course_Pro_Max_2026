"""Glue used by the API layer: score a clip, log the decision, locate the watermark."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .audit import AuditLog, Entry
from .detector import toy_detector_score
from .localize import Segment, locate


@dataclass(frozen=True)
class Check:
    entry: Entry
    segments: list[Segment]


class ProvenanceService:
    def __init__(self, log: AuditLog, model: str, threshold: float, sample_rate: int = 16000) -> None:
        self.log = log
        self.model = model
        self.threshold = threshold
        self.sample_rate = sample_rate

    def check(self, clip: str, audio: list[float], watermark: list[float], at: datetime) -> Check:
        """Score the clip and log the decision, then locate the watermarked segments.

        watermark holds the watermark detector's probability for every sample of the clip.
        """
        score = toy_detector_score(audio, self.sample_rate)
        entry = self.log.record(clip, self.model, self.threshold, score, at)
        return Check(entry, locate(watermark, self.sample_rate))
