"""The lesson's four deterministic prompt-response rubric components."""
from __future__ import annotations

import json
import re


CRITERIA = ("length_compliant", "keyword_coverage", "no_violations", "format_valid")


def score_response(response_text: str, criteria: dict) -> dict:
    """Score the enabled rubric components and their unweighted mean.

    max_words uses whitespace words. Keyword/forbidden matches are case-
    insensitive substrings, preserve criteria order, and empty required words
    have coverage 1. JSON means any complete value json.loads accepts.
    bullet_points follows the lesson's Python heuristic: at least half of
    nonblank stripped lines begin with '-', '*' or '1' (empty text passes).
    numbered_list needs at least two lines beginning with digits then '.'.
    An unrecognized format name passes, as in the source's fallback branch.
    Composite is rounded to 3 decimals; no enabled components yields 0.0.
    """
    raise NotImplementedError


def compare_models(test_results: dict[str, dict], criteria: dict) -> tuple[dict, list]:
    """Score replay results and rank by descending composite, preserving input ties.

    Each result has response, tokens, api_latency_ms. Return (comparison,
    ranked pairs); the metadata is retained and no input object is mutated.
    """
    raise NotImplementedError
