"""The small JSON Schema 2020-12 subset that the client enforces at runtime."""
from __future__ import annotations

from typing import Any

from .wire import ContractViolation

TYPE_NAMES = ("null", "boolean", "integer", "number", "string", "array", "object")


def is_type(value: Any, name: str) -> bool:
    """JSON Schema type test. bool is not an integer and not a number."""
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
    raise ContractViolation(f"unknown schema type {name!r}")


def check_schema(schema: Any, path: str = "$") -> None:
    """Admission check: the schema uses the enforced keywords with well-formed values.

    type is one type name or a non-empty list of them; properties maps names to schemas;
    required lists names; items is a schema; enum is a list; minLength is a non-negative
    integer; additionalProperties is a boolean or a schema. Other keywords are allowed and
    are not enforced.
    """
    if not isinstance(schema, dict):
        raise ContractViolation(f"{path}: a schema must be an object")
    kind = schema.get("type")
    if kind is not None:
        names = kind if isinstance(kind, list) else [kind]
        if not names or not all(isinstance(name, str) and name in TYPE_NAMES for name in names):
            raise ContractViolation(f"{path}.type: unknown type {kind!r}")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ContractViolation(f"{path}.properties: must be an object")
    for name, child in properties.items():
        check_schema(child, f"{path}.properties.{name}")
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(name, str) for name in required):
        raise ContractViolation(f"{path}.required: must be a list of names")
    if "items" in schema:
        check_schema(schema["items"], f"{path}.items")
    if not isinstance(schema.get("enum", []), list):
        raise ContractViolation(f"{path}.enum: must be a list")
    minimum = schema.get("minLength", 0)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        raise ContractViolation(f"{path}.minLength: must be a non-negative integer")
    extra = schema.get("additionalProperties", True)
    if not isinstance(extra, bool):
        check_schema(extra, f"{path}.additionalProperties")


def validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Check value against an admitted schema. The first problem raises ContractViolation.

    Enforced: type (one name or a list), enum, required, properties, additionalProperties
    (false or a schema), items and minLength. Other keywords are not enforced.
    """
    if "enum" in schema and value not in schema["enum"]:
        raise ContractViolation(f"{path}: value is not in enum")
    kind = schema.get("type")
    if kind is not None:
        names = kind if isinstance(kind, list) else [kind]
        if not any(is_type(value, name) for name in names):
            raise ContractViolation(f"{path}: expected {kind}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                raise ContractViolation(f"{path}.{name}: required property missing")
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in properties:
                validate_json_schema(item, properties[name], f"{path}.{name}")
            elif extra is False:
                raise ContractViolation(f"{path}.{name}: additional property rejected")
            elif isinstance(extra, dict):
                validate_json_schema(item, extra, f"{path}.{name}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate_json_schema(item, schema["items"], f"{path}[{index}]")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ContractViolation(f"{path}: string is shorter than minLength")
