"""Latency budgets: sum a voice chain before shipping it."""
from __future__ import annotations

# Typical 2026 latencies per stage, (best, worst) in ms.
TYPICAL_MS: dict[str, tuple[int, int]] = {
    "vad": (20, 60),
    "stt": (100, 250),
    "llm": (150, 400),  # first token
    "tts": (100, 200),  # first audio
    "transport": (30, 80),  # round trip
}

_FORMS = ("stage", "first", "all", "use")


def latency(spec, library: dict | None = None) -> tuple[int, int]:
    """End-to-end (best, worst) latency of a pipeline spec, in ms.

    A spec is one of:
      "stt"                              a stage with its TYPICAL_MS range
      {"stage": "stt", "ms": [80, 120]}  a stage with a measured range ("ms" is optional)
      [spec, spec, ...]                  a chain: one after another (an empty chain is (0, 0))
      {"first": [spec, ...]}             parallel branches; the first one to finish wins
      {"all": [spec, ...]}               parallel branches; wait until every one finishes
      {"use": "name"}                    the sub-pipeline library[name]

    Sub-pipelines may use other sub-pipelines, and one may be used in several places.
    Raises ValueError for an unknown stage or sub-pipeline, a range whose best is
    negative or above its worst, a parallel block with no branches, a sub-pipeline
    that ends up using itself, or anything else that is not a spec.
    """
    library = library or {}

    def walk(node, using: tuple[str, ...]) -> tuple[int, int]:
        if isinstance(node, str):
            if node not in TYPICAL_MS:
                raise ValueError(f"unknown stage {node!r}")
            return TYPICAL_MS[node]
        if isinstance(node, list):
            best = worst = 0
            for child in node:
                lo, hi = walk(child, using)
                best += lo
                worst += hi
            return best, worst
        if not isinstance(node, dict) or sum(key in node for key in _FORMS) != 1:
            raise ValueError(f"not a pipeline spec: {node!r}")
        if "stage" in node:
            if "ms" not in node:
                return walk(node["stage"], using)
            if node["stage"] not in TYPICAL_MS:
                raise ValueError(f"unknown stage {node['stage']!r}")
            lo, hi = node["ms"]
            if not 0 <= lo <= hi:
                raise ValueError(f"bad range {node['ms']!r} for {node['stage']!r}")
            return lo, hi
        if "use" in node:
            name = node["use"]
            if name not in library:
                raise ValueError(f"unknown sub-pipeline {name!r}")
            if name in using:
                raise ValueError(f"sub-pipeline {name!r} uses itself")
            return walk(library[name], using + (name,))
        branches = node["first"] if "first" in node else node["all"]
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"a parallel block needs branches: {node!r}")
        ranges = [walk(branch, using) for branch in branches]
        pick = min if "first" in node else max
        return pick(lo for lo, _ in ranges), pick(hi for _, hi in ranges)

    return walk(spec, ())


def grade(worst_ms: int) -> str:
    """premium up to 600 ms, common up to 1200 ms, slow up to 1500 ms, broken above."""
    if worst_ms <= 600:
        return "premium"
    if worst_ms <= 1200:
        return "common"
    if worst_ms <= 1500:
        return "slow"
    return "broken"
