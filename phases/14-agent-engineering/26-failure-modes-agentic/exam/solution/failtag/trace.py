"""Agent traces: what the agent was asked, the steps it took, and what it claimed at the end."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

REF = re.compile(r"\$\{(\d+)\}")


@dataclass
class TraceStep:
    kind: str  # "tool_call" or "message"
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"  # "ok" or "error"
    result: str = ""


@dataclass
class Trace:
    tid: str
    user_request: str
    constraints: list[str]
    steps: list[TraceStep]
    final_success_claim: bool
    target_state_changed: bool


def references(step: TraceStep) -> set[int]:
    """Indices of the earlier steps whose results this step uses.

    A step uses the result of step N by writing ${N} (0-based) anywhere inside a string
    argument, at any depth of nested dicts and lists.
    """
    found: set[int] = set()
    stack: list[Any] = [step.args]
    while stack:
        value = stack.pop()
        if isinstance(value, str):
            found.update(int(n) for n in REF.findall(value))
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return found
