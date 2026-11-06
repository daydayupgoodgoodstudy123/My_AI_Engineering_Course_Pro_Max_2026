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
    raise NotImplementedError


def grade(worst_ms: int) -> str:
    """premium up to 600 ms, common up to 1200 ms, slow up to 1500 ms, broken above."""
    raise NotImplementedError
