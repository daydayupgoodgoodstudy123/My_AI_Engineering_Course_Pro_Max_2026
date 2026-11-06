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
    raise NotImplementedError
