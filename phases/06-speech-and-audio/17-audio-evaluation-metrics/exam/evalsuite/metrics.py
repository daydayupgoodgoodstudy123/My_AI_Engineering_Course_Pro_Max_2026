"""What each reported metric means: which way is better, which values are valid, its 0..1 scale."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    lower_is_better: bool
    minimum: float  # valid values lie in [minimum, maximum]
    maximum: float
    worst: float  # on a 0..1 scale, worst maps to 0 and best to 1
    best: float


METRICS = {
    "wer": Metric(True, 0.0, math.inf, worst=1.0, best=0.0),
    "cer": Metric(True, 0.0, math.inf, worst=1.0, best=0.0),
    "eer": Metric(True, 0.0, 1.0, worst=0.5, best=0.0),
    "accuracy": Metric(False, 0.0, 1.0, worst=0.0, best=1.0),
    "utmos": Metric(False, 1.0, 5.0, worst=1.0, best=5.0),
    "mos": Metric(False, 1.0, 5.0, worst=1.0, best=5.0),
}
