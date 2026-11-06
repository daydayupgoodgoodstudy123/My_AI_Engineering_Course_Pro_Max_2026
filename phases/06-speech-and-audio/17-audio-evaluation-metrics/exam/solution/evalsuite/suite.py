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
    scores: dict[str, float | None] = {}

    def visit(node: Suite, path: str, parent: str) -> float | None:
        if "metric" in node:
            if "children" in node:
                raise ValueError(f"{path}: a metric leaf has no children")
            spec = METRICS.get(node["metric"])
            if spec is None:
                raise ValueError(f"{path}: unknown metric {node['metric']!r}")
            value = results.get((parent, node["metric"]))
            score = None
            if value is not None:
                score = min(1.0, max(0.0, (value - spec.worst) / (spec.best - spec.worst)))
        else:
            children = node.get("children")
            if not children:
                raise ValueError(f"{path}: a group needs children")
            counted: list[tuple[float, float | None]] = []
            for child in children:
                weight = child.get("weight", 1)
                if weight < 0:
                    raise ValueError(f"{path}: negative weight")
                below = visit(child, f"{path}/{_name(child)}", node["name"])
                if weight:
                    counted.append((weight, below))
            total = sum(weight for weight, _ in counted)
            if not total:
                raise ValueError(f"{path}: every child has weight 0")
            score = None
            if all(below is not None for _, below in counted):
                score = sum(weight * below for weight, below in counted) / total
        if path in scores:
            raise ValueError(f"two nodes at {path}")
        scores[path] = score
        return score

    if "metric" in suite:
        raise ValueError("the root of a suite is a group")
    visit(suite, _name(suite), "")
    return scores


def _name(node: Suite) -> str:
    name = node.get("metric", node.get("name"))
    if not isinstance(name, str):
        raise ValueError(f"a node needs a name or a metric: {node!r}")
    return name
