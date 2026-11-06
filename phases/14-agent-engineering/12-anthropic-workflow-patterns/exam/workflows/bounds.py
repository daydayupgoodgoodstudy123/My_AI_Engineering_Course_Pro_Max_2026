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
    raise NotImplementedError
