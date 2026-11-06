"""Tool registry: schema validation, argument coercion and sandboxed dispatch.

A JSON Schema subset: required, type (string, integer, number, boolean, array, object), enum,
minimum, maximum and format "date". Every failure goes back to the model as a structured
observation it can act on; nothing raises into the agent loop.
"""
from __future__ import annotations

import datetime
import math
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable

_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    executor: Callable[..., str]
    timeout_s: float = 5.0


@dataclass
class ToolCall:
    tool_use_id: str
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    tool_use_id: str
    ok: bool
    content: str


def _coerce(value: Any, schema: dict[str, Any]) -> tuple[Any, str | None]:
    """Fit one value to its schema type: (value, None) when it fits, else (value, error).

    integer: an int, or a string written exactly as JSON writes an integer: ASCII digits, an
    optional leading "-", no leading zeros ("5" -> 5, "-12" -> -12).
    number: a finite int or float, or a string written exactly as a JSON number ("2.5" -> 2.5,
    "2.15e1" -> 21.5); the result is a float. NaN and the infinities are not numbers here.
    Booleans are never numbers. Anything else is rejected, not guessed at: coerce if
    unambiguous, reject if not.
    """
    t = schema.get("type")
    if t == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            if _INTEGER.fullmatch(value):
                try:
                    return int(value), None
                except ValueError:  # more digits than int() converts
                    pass
            return value, f"cannot coerce string {value!r} to integer"
        return value, f"expected integer, got {type(value).__name__}"
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return value, f"expected number, got {type(value).__name__}"
        if isinstance(value, str) and not _NUMBER.fullmatch(value):
            return value, f"cannot coerce string {value!r} to number"
        try:
            number = float(value)
        except OverflowError:  # an int too large for a float
            number = math.inf
        if not math.isfinite(number):
            return value, f"expected a finite number, got {value!r}"
        return number, None
    if t == "boolean":
        if isinstance(value, bool):
            return value, None
        return value, f"expected boolean, got {type(value).__name__}"
    if t == "string":
        if isinstance(value, str):
            return value, None
        return value, f"expected string, got {type(value).__name__}"
    if t == "array":
        if isinstance(value, list):
            return value, None
        return value, f"expected array, got {type(value).__name__}"
    if t == "object":
        if isinstance(value, dict):
            return value, None
        return value, f"expected object, got {type(value).__name__}"
    return value, None


def _is_date(text: str) -> bool:
    try:
        return datetime.date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False


def validate(args: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Check arguments against an object schema; return (coerced arguments, errors).

    Every problem is reported, not only the first: a missing required field, a field the
    schema does not define, a value of the wrong type, a value outside enum, minimum or
    maximum, and, for format "date", a string that is not a real calendar date written
    YYYY-MM-DD (checked with a date parser, not a pattern).
    """
    errors: list[str] = []
    props = schema.get("properties", {})
    required = schema.get("required", [])
    out: dict[str, Any] = {}

    for name in required:
        if name not in args:
            errors.append(f"missing required: {name}")

    for name, value in args.items():
        prop = props.get(name)
        if prop is None:
            errors.append(f"unknown field: {name}")
            continue
        coerced, err = _coerce(value, prop)
        if err:
            errors.append(f"{name}: {err}")
            continue
        if "enum" in prop and coerced not in prop["enum"]:
            errors.append(f"{name}: {coerced!r} not in {prop['enum']}")
            continue
        if prop.get("type") in ("number", "integer"):
            if "minimum" in prop and coerced < prop["minimum"]:
                errors.append(f"{name}: {coerced} < minimum {prop['minimum']}")
                continue
            if "maximum" in prop and coerced > prop["maximum"]:
                errors.append(f"{name}: {coerced} > maximum {prop['maximum']}")
                continue
        if prop.get("format") == "date" and isinstance(coerced, str) and not _is_date(coerced):
            errors.append(f"{name}: {coerced!r} is not a date (YYYY-MM-DD)")
            continue
        out[name] = coerced

    return out, errors


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def dispatch(self, call: ToolCall) -> ToolResult:
        """Validate one call and run it; every outcome is a ToolResult carrying the call's id.

        An unknown tool, invalid arguments, an executor that raises and an executor still
        running after its tool's timeout_s each come back as ok=False with an observation the
        model can act on. A thread cannot be killed, so on a timeout dispatch stops waiting and
        answers "timeout: <name> did not finish within <timeout_s> s"; the registry keeps
        serving other calls while the stuck one runs on.
        """
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.tool_use_id, False,
                              f"error: unknown tool {call.name!r}")
        validated, errors = validate(call.args, tool.input_schema)
        if errors:
            return ToolResult(call.tool_use_id, False,
                              "validation error: " + "; ".join(errors))
        outcome: dict[str, Any] = {}

        def run() -> None:
            try:
                outcome["content"] = tool.executor(**validated)
            except Exception as e:
                outcome["error"] = e

        worker = threading.Thread(target=run, name=f"tool-{tool.name}", daemon=True)
        worker.start()
        worker.join(tool.timeout_s)
        if worker.is_alive():
            return ToolResult(call.tool_use_id, False,
                              f"timeout: {tool.name} did not finish within {tool.timeout_s} s")
        if "error" in outcome:
            e = outcome["error"]
            return ToolResult(call.tool_use_id, False,
                              f"execution error: {type(e).__name__}: {e}")
        return ToolResult(call.tool_use_id, True, outcome["content"])

    def dispatch_many(self, calls: list[ToolCall]) -> list[ToolResult]:
        """Answer one turn's calls in order; each result carries its call's tool_use_id."""
        return [self.dispatch(c) for c in calls]
