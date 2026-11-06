"""Plans, steps and evidence: what flows from the Planner to the Workers to the Solver."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# An evidence reference. "#E1" is the output of step E1; "#E12" is step E12, not E1 followed by "2".
REF = re.compile(r"#E(\d+)")

# The evidence text the Solver sees for a step that was skipped because a step it depends on failed.
MISSING = "(missing: a step it depends on failed)"

STEP_ID = re.compile(r"E(\d+)")


@dataclass(frozen=True)
class Step:
    """One plan step: call `tool` with `args`.

    args is JSON-like: str, int, float, bool, None, lists and dicts. Any string in it, at any
    depth, may refer to earlier evidence, as in {"query": "population of #E1"}.
    """

    id: str
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Plan:
    steps: list[Step]


@dataclass(frozen=True)
class Evidence:
    """What one step produced. status is "ok", "failed" or "skipped"."""

    status: str
    text: str


def references(value: Any) -> list[str]:
    """The step ids that value refers to, at any depth of lists and dicts, in order of first appearance."""
    found: dict[str, None] = {}

    def walk(item: Any) -> None:
        if isinstance(item, str):
            for digits in REF.findall(item):
                found.setdefault(f"E{digits}", None)
        elif isinstance(item, list):
            for element in item:
                walk(element)
        elif isinstance(item, dict):
            for element in item.values():
                walk(element)

    walk(value)
    return list(found)


def number(step_id: str) -> int:
    """The number of a step id: number("E12") == 12."""
    match = STEP_ID.fullmatch(step_id)
    if match is None:
        raise ValueError(f"step ids look like E1, E2, ...; got {step_id!r}")
    return int(match.group(1))
