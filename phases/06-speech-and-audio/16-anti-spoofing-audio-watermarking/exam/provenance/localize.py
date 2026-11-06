"""Where in a clip is the watermark? AudioSeal-style localization."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """Samples start, start + 1, ..., end - 1 of a clip."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def locate(
    probs: list[float],
    sample_rate: int,
    threshold: float = 0.5,
    min_s: float = 0.1,
    max_gap_s: float = 0.02,
) -> list[Segment]:
    """Watermarked segments of a clip, from the detector's per-sample watermark probabilities.

    A sample is watermarked when its probability is above threshold. Runs of watermarked samples
    with gaps of at most max_gap_s between them are joined into one segment, and then segments
    shorter than min_s are dropped. Durations are rounded to whole samples. Segments are in order.
    """
    raise NotImplementedError


def iou(predicted: list[Segment], truth: list[Segment]) -> float:
    """Intersection over union of two lists of segments, counted in samples.

    Segments within each list are in order and do not overlap. Two empty lists agree (1.0).
    """
    raise NotImplementedError
