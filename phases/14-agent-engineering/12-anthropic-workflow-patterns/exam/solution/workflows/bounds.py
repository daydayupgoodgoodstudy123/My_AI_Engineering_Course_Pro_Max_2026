"""Cost bounds for nested workflow specs.

Workflows beat agents on cost-bound tasks because a workflow's step count is bounded. A spec is a
tree of nodes, plain dicts as loaded from JSON, and its bounds can be worked out before it runs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bounds:
    min_calls: int
    max_calls: int
    worst_ms: int


def bounds(node: dict) -> Bounds:
    """The fewest and the most LLM calls one run of the spec can make, and its worst-case latency.

    Node types, by their "type" key:

        llm                  {"ms": t}: one LLM call that takes t ms
        tool                 {"ms": t}: a tool call, t ms and no LLM call
        chain                {"steps": [node, ...]}: each step after the one before
        route                {"classifier": node, "branches": {label: node, ...}}: the classifier,
                             then exactly one of the branches
        parallel             {"sections": [node, ...]}: every section at the same time, or
                             {"n": k, "node": node}: k copies of one node at the same time (voting)
        orchestrator         {"planner": node, "workers": {name: node, ...}, "synthesizer": node,
                             "max_rounds": r, "max_subtasks": k}: run as orchestrate() runs it, so
                             1 to r rounds, each a planner call and then up to k worker runs at the
                             same time, then one synthesis; a run can stop after round 1 with no
                             worker run at all
        evaluator-optimizer  {"propose": node, "evaluate": node, "max_iter": m}: 1 to m rounds,
                             each a proposal and then its evaluation

    Any other type raises ValueError naming it. The counts n, max_rounds, max_subtasks and max_iter
    must be at least 1 (ValueError otherwise).
    """
    kind = node.get("type")
    if kind == "llm":
        return Bounds(1, 1, node["ms"])
    if kind == "tool":
        return Bounds(0, 0, node["ms"])
    if kind == "chain":
        parts = [bounds(step) for step in node["steps"]]
        return Bounds(
            sum(p.min_calls for p in parts), sum(p.max_calls for p in parts), sum(p.worst_ms for p in parts)
        )
    if kind == "route":
        first = bounds(node["classifier"])
        branches = [bounds(branch) for branch in node["branches"].values()]
        return Bounds(
            first.min_calls + min(b.min_calls for b in branches),
            first.max_calls + max(b.max_calls for b in branches),
            first.worst_ms + max(b.worst_ms for b in branches),
        )
    if kind == "parallel":
        if "sections" in node:
            parts = [bounds(section) for section in node["sections"]]
            return Bounds(
                sum(p.min_calls for p in parts), sum(p.max_calls for p in parts), max(p.worst_ms for p in parts)
            )
        n = _count(node, "n")
        one = bounds(node["node"])
        return Bounds(n * one.min_calls, n * one.max_calls, one.worst_ms)
    if kind == "orchestrator":
        rounds, per_round = _count(node, "max_rounds"), _count(node, "max_subtasks")
        planner, synthesizer = bounds(node["planner"]), bounds(node["synthesizer"])
        workers = [bounds(worker) for worker in node["workers"].values()]
        most = max((w.max_calls for w in workers), default=0)
        slowest = max((w.worst_ms for w in workers), default=0)
        return Bounds(
            planner.min_calls + synthesizer.min_calls,
            rounds * (planner.max_calls + per_round * most) + synthesizer.max_calls,
            rounds * (planner.worst_ms + slowest) + synthesizer.worst_ms,
        )
    if kind == "evaluator-optimizer":
        rounds = _count(node, "max_iter")
        propose, evaluate = bounds(node["propose"]), bounds(node["evaluate"])
        return Bounds(
            propose.min_calls + evaluate.min_calls,
            rounds * (propose.max_calls + evaluate.max_calls),
            rounds * (propose.worst_ms + evaluate.worst_ms),
        )
    raise ValueError(f"unknown node type {kind!r}")


def _count(node: dict, key: str) -> int:
    value = node[key]
    if value < 1:
        raise ValueError(f"{key} must be at least 1, got {value}")
    return value
