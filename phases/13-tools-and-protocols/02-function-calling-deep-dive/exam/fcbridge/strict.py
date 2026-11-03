"""Compile a tool's schema for OpenAI strict mode."""
from __future__ import annotations

from .canonical import Tool


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
    raise NotImplementedError
