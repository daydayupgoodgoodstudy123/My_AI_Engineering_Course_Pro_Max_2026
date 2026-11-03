"""Typed extraction outside strict mode: generate, parse, validate, retry with the errors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .outcome import ParsedResult, feedback, process_model_output
from .schema import INVOICE_SCHEMA, ValidationError


@dataclass
class Extraction:
    """How an extraction ended: the last attempt's result, and how many attempts were made."""

    result: ParsedResult
    attempts: int


def check_totals(payload: dict) -> list[ValidationError]:
    """The rule the schema cannot express: total_usd is exactly the sum of qty * unit_usd.

    payload has already passed INVOICE_SCHEMA. Amounts are compared exactly, as decimals,
    with no rounding and no tolerance. A mismatch is one error at ("total_usd",):
    "expected <the sum>, the sum of qty * unit_usd".
    """
    expected = sum(item["qty"] * item["unit_usd"] for item in payload["line_items"])
    if expected != payload["total_usd"]:
        return [ValidationError(("total_usd",), f"expected {expected}, the sum of qty * unit_usd")]
    return []


def extract_invoice(generate: Callable[[str | None], str], max_retries: int = 3) -> Extraction:
    """generate -> parse -> validate -> check totals; on failure, feed the errors back and retry.

    generate(note) returns the model's raw reply. note is None on the first attempt and, on
    every retry, feedback() of the attempt before it. A reply that passes INVOICE_SCHEMA but
    fails check_totals is a violation with those errors. A refusal ends the extraction at
    once: it is never retried. After max_retries retries, the last result is returned as is.
    """
    note = None
    for attempt in range(1, max_retries + 2):
        result = process_model_output(generate(note), INVOICE_SCHEMA)
        if result.kind == "ok":
            errors = check_totals(result.payload)
            if errors:
                result = ParsedResult("violation", result.payload, errors, result.raw)
        if result.kind in ("ok", "refusal"):
            break
        note = feedback(result)
    return Extraction(result, attempt)
