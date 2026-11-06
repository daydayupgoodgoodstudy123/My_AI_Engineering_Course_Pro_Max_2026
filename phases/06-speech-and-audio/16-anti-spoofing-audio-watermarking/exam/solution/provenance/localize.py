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
    min_len = round(min_s * sample_rate)
    max_gap = round(max_gap_s * sample_rate)
    runs: list[list[int]] = []
    start = None
    for i, p in enumerate(probs):
        if p > threshold:
            if start is None:
                start = i
        elif start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(probs)])

    joined: list[list[int]] = []
    for run in runs:
        if joined and run[0] - joined[-1][1] <= max_gap:
            joined[-1][1] = run[1]
        else:
            joined.append(run)
    return [Segment(s, e) for s, e in joined if e - s >= min_len]


def iou(predicted: list[Segment], truth: list[Segment]) -> float:
    """Intersection over union of two lists of segments, counted in samples.

    Segments within each list are in order and do not overlap. Two empty lists agree (1.0).
    """
    inter = sum(
        max(0, min(p.end, t.end) - max(p.start, t.start)) for p in predicted for t in truth
    )
    union = sum(s.length for s in predicted) + sum(s.length for s in truth) - inter
    return inter / union if union else 1.0
