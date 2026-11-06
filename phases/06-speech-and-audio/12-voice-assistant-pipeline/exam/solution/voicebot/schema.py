"""Check an LLM's tool arguments against the tool's JSON schema, reporting every problem."""
from __future__ import annotations

from typing import Any


def validate(schema: dict, value: Any) -> list[tuple[str, str]]:
    """Every problem with value under schema, as (JSON pointer, problem) pairs; [] if valid.

    The schema language is the JSON-schema subset tool definitions use: type (a name, or a list of
    names, from object, array, string, integer, number, boolean, null), properties, required,
    additionalProperties: false, items, enum, and "$ref": "#/$defs/<name>", resolved against the
    root schema (a definition may refer to itself).

    Problems are "type" (nothing below a value of the wrong type is checked), "missing" (a required
    property; the pointer names the property), "unexpected" (a property that
    additionalProperties: false does not allow) and "enum". A JSON boolean is not an integer or a
    number. Pointers follow RFC 6901: the root is "", and "~" and "/" inside a name are written
    "~0" and "~1". Problems may come in any order.
    """
    problems: list[tuple[str, str]] = []

    def visit(node: dict, value: Any, path: str) -> None:
        while "$ref" in node:
            node = _resolve(schema, node["$ref"])
        types = node.get("type")
        if types is not None:
            names = [types] if isinstance(types, str) else list(types)
            if not any(_is(value, name) for name in names):
                problems.append((path, "type"))
                return
        if "enum" in node and not any(_same(value, option) for option in node["enum"]):
            problems.append((path, "enum"))
        if isinstance(value, dict):
            properties = node.get("properties", {})
            for name in node.get("required", []):
                if name not in value:
                    problems.append((f"{path}/{_escape(name)}", "missing"))
            for name, item in value.items():
                if name in properties:
                    visit(properties[name], item, f"{path}/{_escape(name)}")
                elif node.get("additionalProperties") is False:
                    problems.append((f"{path}/{_escape(name)}", "unexpected"))
        elif isinstance(value, list) and "items" in node:
            for index, item in enumerate(value):
                visit(node["items"], item, f"{path}/{index}")

    visit(schema, value, "")
    return problems


def _resolve(root: dict, ref: str) -> dict:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise ValueError(f"only local #/$defs/ references are supported, got {ref!r}")
    return root["$defs"][ref[len(prefix):]]


def _is(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    raise ValueError(f"unknown type {name!r}")


def _same(value: Any, option: Any) -> bool:
    return value == option and isinstance(value, bool) == isinstance(option, bool)


def _escape(name: str) -> str:
    return name.replace("~", "~0").replace("/", "~1")
