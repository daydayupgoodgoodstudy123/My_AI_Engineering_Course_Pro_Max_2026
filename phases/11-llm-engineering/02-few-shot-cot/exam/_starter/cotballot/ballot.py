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
    raise NotImplementedError


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
    raise NotImplementedError
