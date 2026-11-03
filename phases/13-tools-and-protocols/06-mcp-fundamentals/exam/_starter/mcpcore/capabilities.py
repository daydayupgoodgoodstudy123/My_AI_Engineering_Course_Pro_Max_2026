"""Client capability requirements, written as nested capability objects."""
from __future__ import annotations

from typing import Any


def missing_capabilities(required: dict[str, Any], declared: Any) -> dict[str, Any]:
    """The part of required that declared does not satisfy ({} when nothing is missing).

    Both are nested capability objects such as
    {"extensions": {"io.modelcontextprotocol/tasks": {}}}. A key of required is satisfied
    when declared has the same key with an object value and, if the required value has keys
    of its own, those are satisfied inside it. An empty object declares support; true, null,
    lists and other values that are not objects do not. Keys are compared whole:
    "io.modelcontextprotocol/tasks" is one key, dots and slash included.

    The result keeps only what is missing, and shares no objects with required.
    """
    raise NotImplementedError
