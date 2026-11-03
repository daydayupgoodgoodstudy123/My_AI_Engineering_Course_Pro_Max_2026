"""A JSON Schema 2020-12 subset for checking model output, with typed error locations.

Keywords: type, properties, required, additionalProperties, items, enum, minimum, maximum,
minLength, maxLength and pattern, plus oneOf (see _one_of).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Union

Loc = tuple[Union[str, int], ...]

INVOICE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "customer": {"type": "string", "minLength": 1, "maxLength": 200},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
                    "qty": {"type": "integer", "minimum": 1},
                    "unit_usd": {"type": "number", "minimum": 0},
                },
                "required": ["sku", "qty", "unit_usd"],
                "additionalProperties": False,
            },
        },
        "total_usd": {"type": "number", "minimum": 0},
        "currency": {"type": "string", "enum": ["USD", "EUR", "INR"]},
    },
    "required": ["customer", "line_items", "total_usd", "currency"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ValidationError:
    """One problem in a document.

    loc is a typed location, like a Pydantic error's loc: a str steps into an object member,
    an int into an array element. ("line_items", 0, "sku") is written $.line_items[0].sku.
    """

    loc: Loc
    message: str

    @property
    def path(self) -> str:
        return "$" + "".join(f"[{step}]" if isinstance(step, int) else f".{step}" for step in self.loc)

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate(schema: dict, value: Any, loc: Loc = ()) -> list[ValidationError]:
    """Every error in value against schema, each at its own location.

    Numbers are int, float or Decimal; a bool is never a number. enum compares JSON values:
    false is not 0 and true is not 1, 1 equals 1.0, and two objects are equal when they have
    the same members, whatever their key order. A schema with oneOf is checked by _one_of.
    """
    if "oneOf" in schema:
        return _one_of(schema, value, loc)
    errors: list[ValidationError] = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return [ValidationError(loc, f"expected object, got {type(value).__name__}")]
        props = schema.get("properties", {})
        for field in schema.get("required", []):
            if field not in value:
                errors.append(ValidationError(_at(loc, field), "missing required field"))
        if schema.get("additionalProperties") is False:
            for extra in value:
                if extra not in props:
                    errors.append(ValidationError(_at(loc, extra), "additional property not allowed"))
        for key, sub in props.items():
            if key in value:
                errors.extend(validate(sub, value[key], _at(loc, key)))
        return errors
    if t == "array":
        if not isinstance(value, list):
            return [ValidationError(loc, f"expected array, got {type(value).__name__}")]
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                errors.extend(validate(item_schema, item, _at(loc, i)))
        return errors
    if t == "string":
        if not isinstance(value, str):
            return [ValidationError(loc, f"expected string, got {type(value).__name__}")]
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(ValidationError(loc, f"shorter than minLength {schema['minLength']}"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(ValidationError(loc, f"longer than maxLength {schema['maxLength']}"))
        if "pattern" in schema and not re.match(schema["pattern"], value):
            errors.append(ValidationError(loc, f"does not match pattern {schema['pattern']!r}"))
    elif t == "number":
        if not _is_number(value):
            return [ValidationError(loc, f"expected number, got {type(value).__name__}")]
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return [ValidationError(loc, f"expected integer, got {type(value).__name__}")]
    elif t == "boolean":
        if not isinstance(value, bool):
            return [ValidationError(loc, f"expected boolean, got {type(value).__name__}")]
    if "minimum" in schema and _is_number(value) and value < schema["minimum"]:
        errors.append(ValidationError(loc, f"below minimum {schema['minimum']}"))
    if "maximum" in schema and _is_number(value) and value > schema["maximum"]:
        errors.append(ValidationError(loc, f"above maximum {schema['maximum']}"))
    if "enum" in schema and not _in_enum(value, schema["enum"]):
        errors.append(ValidationError(loc, f"value {value!r} not in enum"))
    return errors


def _one_of(schema: dict, value: Any, loc: Loc) -> list[ValidationError]:
    """oneOf, optionally with an OpenAPI-style discriminator: {"propertyName": "kind"}.

    With a discriminator, every branch is an object schema that names its tag in
    properties[propertyName].enum. The value's tag picks the branch, and only that branch's
    errors are reported. A value that is not an object gets "expected object, got <type>" at
    loc; a missing tag gets "missing required field" and an unknown tag "value <tag!r> not in
    enum", both at the tag's own location.

    Without a discriminator, the value must match exactly one branch: no match is
    "matches none of the oneOf branches", several are "matches <n> oneOf branches, expected
    exactly one", both at loc.
    """
    branches = schema["oneOf"]
    discriminator = schema.get("discriminator")
    if discriminator is None:
        matches = sum(1 for branch in branches if not validate(branch, value, loc))
        if matches == 1:
            return []
        if matches == 0:
            return [ValidationError(loc, "matches none of the oneOf branches")]
        return [ValidationError(loc, f"matches {matches} oneOf branches, expected exactly one")]
    if not isinstance(value, dict):
        return [ValidationError(loc, f"expected object, got {type(value).__name__}")]
    tag = discriminator["propertyName"]
    if tag not in value:
        return [ValidationError(_at(loc, tag), "missing required field")]
    for branch in branches:
        if _in_enum(value[tag], branch["properties"][tag]["enum"]):
            return validate(branch, value, loc)
    return [ValidationError(_at(loc, tag), f"value {value[tag]!r} not in enum")]


def _at(loc: Loc, step: str | int) -> Loc:
    return loc + (step,)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


# Enum lists already turned into sets of keys, by id. Each entry keeps its list alive, so the
# id cannot be reused by another list while the entry exists.
_ENUM_KEYS: dict[int, tuple[list, frozenset]] = {}


def _in_enum(value: Any, options: list) -> bool:
    entry = _ENUM_KEYS.get(id(options))
    if entry is None:
        if len(_ENUM_KEYS) >= 1024:
            _ENUM_KEYS.clear()
        entry = (options, frozenset(_json_key(option) for option in options))
        _ENUM_KEYS[id(options)] = entry
    return _json_key(value) in entry[1]


def _json_key(value: Any) -> tuple:
    """A hashable stand-in for a JSON value: two keys are equal exactly when the values are (see validate)."""
    if isinstance(value, bool):
        return ("boolean", value)
    if _is_number(value):
        return ("number", value)
    if isinstance(value, list):
        return ("array", tuple(_json_key(v) for v in value))
    if isinstance(value, dict):
        return ("object", frozenset((k, _json_key(v)) for k, v in value.items()))
    return (type(value).__name__, value)


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


def lookup(document: Any, loc: Loc) -> Any:
    """The value at loc inside document, or MISSING when the document has nothing there."""
    node = document
    for step in loc:
        try:
            node = node[step]
        except (KeyError, IndexError):
            return MISSING
    return node
