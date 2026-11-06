"""Audit a supplied Tree-of-Thought trace without running a search or a model."""
from __future__ import annotations

import math

from .ballot import canonical, normalize_answer
from .examples import extract_answer


def trace_report(roots: list[dict], selected_answer: str | None = None) -> dict:
    """Report every explicit numeric-answer path in supplied depth-first order.

    Each node has id, text, score, generation_tokens, evaluation_tokens,
    children. One node represents one generation call plus one evaluation
    call; token fields are supplied total tokens for those two calls.
    Terminals contain a valid final-answer marker, and may have children.
    Each path includes all ancestor ids, 2 calls per path node, summed tokens,
    canonical answer, terminal score and whether it equals selected_answer.
    Global totals bill each id once, even if a shared node occurs in several
    paths. Repeated id on the current path is a cycle; conflicting records for
    one id raise ValueError. Scores are finite in [0,1], tokens nonnegative
    integers. A nonnumeric selected_answer raises ValueError. Do not prune
    low-score branches or stop visiting siblings after finding an answer.
    """
    raise NotImplementedError
