"""Exact finite-grammar numeric ballots over replayed final-answer text."""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from fractions import Fraction

from .examples import extract_answer


INTEGER = r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)"
DECIMAL = re.compile(rf"[+-]?(?:{INTEGER}(?:\.[0-9]+)?|\.[0-9]+)\Z")
RATIONAL = re.compile(rf"([+-]?{INTEGER})/({INTEGER})\Z")


def normalize_answer(answer: str | None) -> Fraction | None:
    """Return an exact numeric value or None for an invalid/absent answer.

    Grammar: an optional leading '$', then a signed integer/finite decimal,
    or signed integer / positive unsigned integer, without internal spaces.
    Integers are ASCII digits, optionally valid 3-digit comma groups. A decimal
    may start with '.', but must have digits after its point. No exponents,
    units, underscores, NaN/Infinity, decimal fractions or zero denominator.
    Surrounding whitespace is ignored. This finite grammar is a local extension
    of the lesson's terminal numeric extractor, not provider behavior.
    """
    if answer is None:
        return None
    value = answer.strip()
    if value.startswith("$"):
        value = value[1:]
    rational = RATIONAL.fullmatch(value)
    if rational is not None:
        numerator, denominator = (int(part.replace(",", "")) for part in rational.groups())
        return Fraction(numerator, denominator) if denominator else None
    if DECIMAL.fullmatch(value) is None:
        return None
    return Fraction(Decimal(value.replace(",", "")))


def canonical(value: Fraction) -> str:
    """Use an integer for denominator 1; otherwise numerator/denominator."""
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def tally_samples(reasonings: list[str]) -> dict:
    """Vote on exact terminal values, retaining every original reasoning sample.

    Return winner, confidence, attempted, valid, raw_answers, answers, votes,
    reasonings. Confidence is winner votes / valid samples, not / attempted;
    an empty valid ballot has winner None and confidence 0.0. Ties choose the
    numerically smaller exact value. Votes are emitted in numeric order.
    """
    raw = [extract_answer(text) for text in reasonings]
    values = [normalize_answer(answer) for answer in raw]
    counts = Counter(value for value in values if value is not None)
    valid = sum(counts.values())
    if counts:
        highest = max(counts.values())
        winner = min(value for value, count in counts.items() if count == highest)
    else:
        winner = None
    return {
        "winner": canonical(winner) if winner is not None else None,
        "confidence": counts[winner] / valid if winner is not None else 0.0,
        "attempted": len(reasonings), "valid": valid,
        "raw_answers": raw,
        "answers": [canonical(value) if value is not None else None for value in values],
        "votes": {canonical(value): counts[value] for value in sorted(counts)},
        "reasonings": list(reasonings),
    }
