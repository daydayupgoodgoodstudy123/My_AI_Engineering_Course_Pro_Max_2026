"""Admission audit of x-mcp-header annotations: where they sit and what they may say."""
from __future__ import annotations

from typing import Any, NamedTuple

from .wire import HEADER_TOKEN

ANNOTATION = "x-mcp-header"
MIRRORABLE_TYPES = frozenset({"string", "integer", "boolean"})
SENSITIVE_NAMES = frozenset({"api_key", "apikey", "authorization", "password", "secret", "token"})
REASONS = ("output", "placement", "name", "type", "duplicate", "sensitive")


class Finding(NamedTuple):
    path: str  # JSON Pointer from the descriptor root, e.g. /inputSchema/properties/region
    reason: str  # one of REASONS


def audit_header_annotations(tool: dict[str, Any]) -> list[Finding]:
    """Every x-mcp-header annotation in a descriptor that admission must refuse, sorted by path.

    Walk all of inputSchema and outputSchema as JSON: every object and every array, under any
    keyword, and every definition whether or not a $ref uses it. Do not follow $ref. An
    annotation is judged where it is written, so a definition reached through $ref is not a
    direct property, and a definition used twice is still one annotation.

    The path is a JSON Pointer (RFC 6901) from the descriptor root: "~" is written "~0" and
    "/" is written "~1" inside a name, and array items are numbered from 0.

    Each annotation gets at most one finding, the first of these that applies:

        output     it is inside outputSchema
        placement  it is anywhere but a direct member of inputSchema.properties
        name       the header name is not a string matching HEADER_TOKEN in full
        type       the property's type is not exactly one of MIRRORABLE_TYPES
        duplicate  an earlier property (in inputSchema.properties order) already uses this
                   header name, ignoring case
        sensitive  the property name or the header name, ignoring case, is in SENSITIVE_NAMES
    """
    raise NotImplementedError
