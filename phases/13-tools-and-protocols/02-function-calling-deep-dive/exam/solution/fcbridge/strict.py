"""Compile a tool's schema for OpenAI strict mode."""
from __future__ import annotations

import copy

from .canonical import Tool
from .limits import LIMITS, LimitError, schema_depth

REF_PREFIX = "#/$defs/"


def strict_tool(tool: Tool) -> Tool:
    """The same tool, marked strict, with a schema that OpenAI strict mode accepts.

    Strict mode allows no $ref, and wants additionalProperties: false and every property listed in
    required, on every object. So the compiled schema:
    - replaces each {"$ref": "#/$defs/<name>"} with its own copy of that definition, and has no $defs;
    - gives every object, wherever it sits (properties, array items, anyOf branches),
      additionalProperties: false and a required list naming all its properties, in order;
    - makes each property that was optional nullable instead, the way WEATHER does with units: its
      type gains "null" at the end, or, for an anyOf, a {"type": "null"} branch at the end;
    - adds None to every enum whose type allows null, which WEATHER's units lacks.

    The input tool is left as it was. Raises LimitError when the compiled schema nests deeper than
    OpenAI's max_depth.
    """
    schema = _compile(tool.input_schema, tool.input_schema.get("$defs", {}))
    depth = schema_depth(schema)
    limit = LIMITS["openai"].max_depth
    if depth > limit:
        raise LimitError(
            f"openai: {tool.name} nests {depth} objects deep once its $refs are inlined; strict mode allows {limit}"
        )
    return Tool(tool.name, tool.description, schema, strict=True)


def _compile(node: dict, defs: dict) -> dict:
    """A fresh compiled copy of one schema node; nothing in it is shared with the input or another copy."""
    if "$ref" in node:
        ref = node["$ref"]
        if not ref.startswith(REF_PREFIX) or ref[len(REF_PREFIX):] not in defs:
            raise ValueError(f"unknown $ref {ref!r}")
        siblings = {k: v for k, v in node.items() if k != "$ref"}
        return _compile({**defs[ref[len(REF_PREFIX):]], **siblings}, defs)
    out: dict = {}
    for key, value in node.items():
        if key == "$defs":
            continue
        if key == "properties":
            out[key] = {name: _compile(sub, defs) for name, sub in value.items()}
        elif key == "items" and isinstance(value, dict):
            out[key] = _compile(value, defs)
        elif key == "anyOf":
            out[key] = [_compile(branch, defs) for branch in value]
        else:
            out[key] = copy.deepcopy(value)
    if "object" in _types(out):
        properties = out.setdefault("properties", {})
        required = set(node.get("required", []))
        for name in properties:
            if name not in required:
                properties[name] = _nullable(properties[name])
        out["required"] = list(properties)
        out["additionalProperties"] = False
    _enum_allows_null(out)
    return out


def _nullable(schema: dict) -> dict:
    if "type" in schema:
        types = _types(schema)
        if "null" not in types:
            schema["type"] = types + ["null"]
    elif "anyOf" in schema and {"type": "null"} not in schema["anyOf"]:
        schema["anyOf"].append({"type": "null"})
    _enum_allows_null(schema)
    return schema


def _enum_allows_null(schema: dict) -> None:
    if "null" in _types(schema) and "enum" in schema and None not in schema["enum"]:
        schema["enum"].append(None)


def _types(schema: dict) -> list[str]:
    kind = schema.get("type", [])
    return [kind] if isinstance(kind, str) else list(kind)
