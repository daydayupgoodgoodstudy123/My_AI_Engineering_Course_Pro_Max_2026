"""Schema-first state: the schemas of agent_state.json and task_board.json, and their validator.

validate() implements the subset of JSON Schema the workbench uses: type, enum, pattern,
required, properties, additionalProperties (false only) and items.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any


class SchemaError(Exception):
    """A value does not match its schema. The message starts with the JSON path of the value."""


class VersionError(SchemaError):
    """A state document is at a schema_version this code cannot load or migrate."""


STATE_SCHEMA: dict[str, Any] = {
    "$id": "agent_state.schema.json",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "active_task_id", "touched_files", "risks", "next_action", "last_human_touch"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [3]},
        "active_task_id": {"type": ["string", "null"], "pattern": r"^T-\d{3,}$"},
        "touched_files": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
        "last_human_touch": {"type": ["number", "null"]},
    },
}

# Tasks may carry fields of the team's own (estimates, labels); the board pins the ones the
# workbench reads.
BOARD_SCHEMA: dict[str, Any] = {
    "$id": "task_board.schema.json",
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "goal", "owner", "acceptance", "status"],
        "properties": {
            "id": {"type": "string", "pattern": r"^T-\d{3,}$"},
            "goal": {"type": "string"},
            "owner": {"type": "string", "enum": ["builder", "reviewer", "human"]},
            "acceptance": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string", "enum": ["todo", "in_progress", "done", "blocked"]},
            "priority": {"enum": [1, 2, 3, "someday"]},
            "needs_review": {"type": "boolean"},
        },
    },
}


def with_tracked_files(schema: dict[str, Any], tracked: list[str]) -> dict[str, Any]:
    """A copy of a state schema whose touched_files may only name files the repo tracks."""
    out = copy.deepcopy(schema)
    out["properties"]["touched_files"]["items"]["enum"] = list(tracked)
    return out


def _check_type(value: Any, types: str | list[str]) -> bool:
    """True when value has one of the JSON types named.

    integer is an int that is not a bool (1.0 is a number, not an integer). number is an int
    or a finite float, never a bool: JSON has no NaN or Infinity. boolean is True or False.
    """
    type_list = [types] if isinstance(types, str) else types
    for t in type_list:
        if t == "object" and isinstance(value, dict):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "string" and isinstance(value, str):
            return True
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if (
            t == "number"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (isinstance(value, int) or math.isfinite(value))
        ):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "null" and value is None:
            return True
    return False


def _key(value: Any) -> Any:
    """Correct supplied typed-JSON key; booleans differ from equal-valued numbers.

    Arrays retain order; object keys do not. Numeric 1 and 1.0 share a key.
    """
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if value is None:
        return ("null",)
    if isinstance(value, list):
        return ("array", tuple(_key(v) for v in value))
    if isinstance(value, dict):
        return ("object", frozenset((k, _key(v)) for k, v in value.items()))
    raise SchemaError(f"{value!r} is not a JSON value")


def _preview(options: list) -> str:
    shown = ", ".join(repr(option) for option in options[:8])
    return f"[{shown}, ...]" if len(options) > 8 else f"[{shown}]"


def validate(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Raise SchemaError, naming the JSON path, for the first part of value that breaks schema.

    - type: one JSON type name or a list of them (see _check_type).
    - enum: value equals one of the options as JSON values: a boolean only equals a boolean,
      numbers are equal when their values are (1 and 1.0), arrays item by item, objects key by key.
    - pattern: a regular expression the whole string must match: nothing may come before
      or after the match, not even a newline.
    - required, properties: keys that must be present, and the schemas of known keys.
    - additionalProperties: false refuses keys that properties does not list; without it,
      other keys are allowed.
    - items: the schema of every array item.

    validate reads the schema as it is at the time of the call.
    """
    # Supplied enum index lives for this top-level call only; schemas may change.
    _validate(value, schema, path, {})


def _validate(value: Any, schema: dict[str, Any], path: str, enums: dict[int, set]) -> None:
    if "type" in schema and not _check_type(value, schema["type"]):
        raise SchemaError(f"{path}: expected {schema['type']}, got {type(value).__name__}")
    # Correct supplied enum membership shares only this invocation's index.
    if "enum" in schema:
        options = schema["enum"]
        keys = enums.get(id(options))
        if keys is None:
            keys = enums[id(options)] = {_key(option) for option in options}
        if _key(value) not in keys:
            raise SchemaError(f"{path}: {value!r} not in {_preview(options)}")
    if "pattern" in schema and isinstance(value, str) and not re.fullmatch(schema["pattern"], value):
        raise SchemaError(f"{path}: {value!r} does not match /{schema['pattern']}/")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{path}: missing required field {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise SchemaError(f"{path}: unexpected fields {unexpected}")
        for key, sub in properties.items():
            if key in value:
                _validate(value[key], sub, f"{path}.{key}", enums)
    if isinstance(value, list) and "items" in schema:
        for idx, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{idx}]", enums)
