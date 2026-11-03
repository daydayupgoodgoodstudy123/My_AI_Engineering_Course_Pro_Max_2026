"""The three failure modes: turn one raw model reply into a typed outcome."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .schema import MISSING, ValidationError, lookup, validate

REFUSAL_PREFIX = "__REFUSAL__"


@dataclass
class ParsedResult:
    """One model reply, classified.

    kind is "ok", "violation", "parse_error" or "refusal". payload is the parsed JSON for ok
    and violation, the stated reason for a refusal, and None for a parse error. raw is the
    reply exactly as the model sent it.
    """

    kind: str
    payload: Any
    errors: list[ValidationError] = field(default_factory=list)
    raw: str = ""


def process_model_output(raw: str, schema: dict) -> ParsedResult:
    """Classify one reply: refusal, parse error, schema violation or ok.

    A reply that starts with REFUSAL_PREFIX is a refusal; it is never parsed, and its payload
    is the reason after the prefix, stripped of surrounding whitespace. Anything else must be
    a single JSON value. Numbers with a fraction or exponent become Decimal, so amounts keep
    exactly the digits the model wrote.
    """
    try:
        parsed = json.loads(raw, parse_float=Decimal)
    except json.JSONDecodeError as e:
        return ParsedResult("parse_error", None, [ValidationError((), str(e))], raw)
    if raw.startswith(REFUSAL_PREFIX):
        return ParsedResult("refusal", raw.removeprefix(REFUSAL_PREFIX).strip(), [], raw)
    errors = validate(schema, parsed)
    if errors:
        return ParsedResult("violation", parsed, errors, raw)
    return ParsedResult("ok", parsed, [], raw)


def feedback(result: ParsedResult) -> str:
    """The note sent back to the model after a failed attempt.

    One line per error, "<path>: <message>", followed by " (value: <JSON>)" when the reply
    has a value at that location.
    """
    lines = []
    for error in result.errors:
        found = MISSING if result.payload is None else lookup(result.payload, error.loc)
        lines.append(str(error) if found is MISSING else f"{error} (value: {json_text(found)})")
    return "\n".join(lines)


def json_text(value: Any) -> str:
    """Compact JSON text for a parsed value; a Decimal is written with exactly its own digits."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(json_text(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{json_text(v)}" for k, v in value.items()) + "}"
    return json.dumps(value, ensure_ascii=False)
