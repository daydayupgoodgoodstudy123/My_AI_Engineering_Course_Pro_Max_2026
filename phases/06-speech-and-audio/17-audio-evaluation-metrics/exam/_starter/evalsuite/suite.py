"""Score a nested evaluation suite: suite -> task -> subset -> metric, with weights."""
from __future__ import annotations

from .metrics import METRICS

# A group is {"name": str, "children": [node, ...]}; a metric leaf is {"metric": str}.
# Any node may carry a "weight" (default 1), relative to its siblings.
Suite = dict


def suite_scores(suite: Suite, results: dict[tuple[str, str], float]) -> dict[str, float | None]:
    """Score every node of a suite on a 0..1 scale, from the metric leaves up.

    A leaf reads results[(name of its parent, its metric)] and maps it onto 0..1 with METRICS:
    the metric's worst value scores 0, its best 1, clamped to that range. A group scores the
    weighted mean of its children. A leaf without a result has no score (None), and so does
    every group with a child that is None and has a nonzero weight: a missing result is never
    averaged away. A child with weight 0 is reported but does not count.
    Returns {path: score} for every node, where a path joins the names from the root with "/"
    and a leaf's name is its metric. Unknown metrics and malformed nodes raise ValueError.
    """
    raise NotImplementedError
