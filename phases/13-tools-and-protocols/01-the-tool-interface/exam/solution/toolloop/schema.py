"""A minimal JSON Schema subset for tool arguments, in the standard library only."""
from __future__ import annotations

from typing import Any


def validate(schema: dict, value: Any) -> list[str]:
    """Every way value breaks schema, as readable messages; [] when it is valid.

    Supports "type" (object, number, string), "properties", "required" and "enum".
    Types are JSON types, so true and false are booleans, never numbers.
    """
    errors: list[str] = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return [f"expected object, got {type(value).__name__}"]
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"missing required field '{field}'")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors.extend(validate(sub, value[key]))
        return errors
    if t == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        errors.append(f"expected number, got {type(value).__name__}")
    if t == "string" and not isinstance(value, str):
        errors.append(f"expected string, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"value {value!r} not in enum {schema['enum']}")
    return errors
