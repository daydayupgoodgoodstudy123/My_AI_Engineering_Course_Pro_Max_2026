"""Mastra-shaped primitives: typed tools, an agent that calls them, and a workflow of steps."""
from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

_TYPE_NAMES = {str: "string", int: "number", float: "number", bool: "boolean", type(None): "null"}


@dataclass(frozen=True)
class MastraTool:
    id: str
    description: str
    input_schema: dict[str, str]  # field -> "string" | "number" | "boolean"
    execute: Callable[..., str]


def check_input(schema: Mapping[str, str], args: Mapping[str, Any]) -> str | None:
    """The first way args break the schema, or None when they fit.

    Every field the schema lists is required. Fields are checked one at a time, in the schema's
    order, and the first problem is returned: "missing field <key>" when args lack the field, or
    "field <key>: expected <type>, got <type>" when its value has another type (None is "null").
    Fields the schema does not list are not checked.
    """
    for key, value in args.items():
        if key not in schema:
            continue
        got = _TYPE_NAMES.get(type(value), type(value).__name__)
        if got != schema[key]:
            return f"field {key}: expected {schema[key]}, got {got}"
    return None


class MastraAgent:
    def __init__(self, name: str, instructions: str, tools: Iterable[MastraTool]) -> None:
        self.name = name
        self.instructions = instructions
        self.tools = {tool.id: tool for tool in tools}

    def run(
        self, prompt: str, calls: list[tuple[str, dict[str, Any]]]
    ) -> tuple[str, list[tuple[str, str]]]:
        """Run the tool calls in order and return (output, trace).

        Each trace entry is (tool id, result). An unknown tool records "error: unknown tool".
        Arguments that break the tool's input_schema record "error: <problem>", and the tool is
        not called. Either way the run goes on with the next call.
        """
        trace: list[tuple[str, str]] = []
        for tool_id, args in calls:
            tool = self.tools.get(tool_id)
            if tool is None:
                trace.append((tool_id, "error: unknown tool"))
                continue
            problem = check_input(tool.input_schema, args)
            if problem is not None:
                trace.append((tool_id, f"error: {problem}"))
            trace.append((tool_id, tool.execute(**args)))
        return f"{self.name} processed {len(calls)} tools", trace


class Workflow:
    """Steps run in order, each on the previous step's output.

    A step may change its input in place and return it. run() returns one (step name, output)
    entry per step, and each entry holds that step's output as it was when the step returned.
    """

    def __init__(self, steps: Iterable[tuple[str, Callable[[Any], Any]]]) -> None:
        self.steps = list(steps)

    def run(self, payload: Any) -> list[tuple[str, Any]]:
        trace: list[tuple[str, Any]] = []
        current = payload
        for name, fn in self.steps:
            current = fn(current)
            trace.append((name, copy.deepcopy(current)))
        return trace
