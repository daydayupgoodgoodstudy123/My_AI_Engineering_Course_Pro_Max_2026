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
    selected = normalize_answer(selected_answer)
    if selected_answer is not None and selected is None:
        raise ValueError("selected answer is not a valid numeric value")
    seen = {}
    terminals = []

    def visit(node: dict, path: list[str], tokens: int) -> None:
        node_id = node["id"]
        if node_id in path:
            raise ValueError(f"thought cycle at {node_id}")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("thought id must be a nonempty string")
        score = node["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("thought score must be finite in [0,1]")
        generation, evaluation = node["generation_tokens"], node["evaluation_tokens"]
        if type(generation) is not int or type(evaluation) is not int or min(generation, evaluation) < 0:
            raise ValueError("thought token counts must be nonnegative integers")
        signature = (node["text"], score, generation, evaluation, tuple(child["id"] for child in node["children"]))
        if node_id in seen and seen[node_id] != signature:
            raise ValueError(f"conflicting thought id {node_id}")
        seen[node_id] = signature
        next_path = path + [node_id]
        next_tokens = tokens + generation + evaluation
        answer = normalize_answer(extract_answer(node["text"]))
        if answer is not None:
            terminals.append({"path": next_path, "answer": canonical(answer), "score": score,
                              "calls": 2 * len(next_path), "tokens": next_tokens,
                              "selected": selected is not None and answer == selected})
        for child in node["children"]:
            visit(child, next_path, next_tokens)

    for root in roots:
        visit(root, [], 0)
    return {"terminals": terminals,
            "totals": {"nodes": len(seen), "calls": 2 * len(seen),
                       "tokens": sum(signature[2] + signature[3] for signature in seen.values())}}
