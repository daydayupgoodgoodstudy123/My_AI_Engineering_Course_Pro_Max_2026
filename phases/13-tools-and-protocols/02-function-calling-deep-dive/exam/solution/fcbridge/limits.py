"""Per-provider request limits, from the lesson's "Limits you will actually hit"."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .canonical import Tool


class LimitError(ValueError):
    """A request the provider would reject. The message starts with the provider's name."""


@dataclass(frozen=True)
class Limits:
    max_tools: int
    max_depth: int | None  # None: no depth limit
    max_argument_bytes: int | None  # UTF-8 bytes of one call's arguments text; None: no limit


LIMITS = {
    "openai": Limits(max_tools=128, max_depth=5, max_argument_bytes=8192),
    "anthropic": Limits(max_tools=64, max_depth=10, max_argument_bytes=None),  # 10: the practical limit
    "gemini": Limits(max_tools=64, max_depth=None, max_argument_bytes=None),
}


def schema_depth(schema: dict) -> int:
    """How many objects deep a schema nests.

    An object of plain fields is 1 deep, and every object nested inside it, through properties,
    array items or anyOf branches, adds one. $ref is not followed: measure a schema whose
    references are inlined (strict_tool does that).
    """
    own = 1 if "object" in _types(schema) else 0
    return own + max((schema_depth(sub) for sub in _subschemas(schema)), default=0)


def check_depth(provider: str, tools: list[Tool]) -> None:
    """Raise LimitError when a tool's schema nests deeper than the provider accepts."""
    limit = LIMITS[provider].max_depth
    if limit is None:
        return
    for tool in tools:
        depth = schema_depth(tool.input_schema)
        if depth > limit:
            raise LimitError(f"{provider}: {tool.name} nests {depth} objects deep; the limit is {limit}")


def _types(schema: dict) -> list[str]:
    kind = schema.get("type", [])
    return [kind] if isinstance(kind, str) else list(kind)


def _subschemas(schema: dict) -> Iterator[dict]:
    yield from schema.get("properties", {}).values()
    if isinstance(schema.get("items"), dict):
        yield schema["items"]
    yield from schema.get("anyOf", [])
