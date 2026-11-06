"""Guardrails the support desk uses. Each has a name and check(text) -> (ok, reason)."""
from __future__ import annotations

import re


class PiiGuard:
    """Input guardrail: refuses text that contains an ID number matched by one of the rules.

    rules is a list of (name, pattern) pairs, and the patterns are regular expressions. Rules are
    tried in order; the reason names the first rule that matches.
    """

    def __init__(self, rules: list[tuple[str, str]], name: str = "pii") -> None:
        self.name = name
        self.rules = list(rules)

    def check(self, text: str) -> tuple[bool, str]:
        for rule, pattern in self.rules:
            if re.search(pattern, text):
                return False, f"matches PII rule {rule}"
        return True, "ok"


class LengthCap:
    """Output guardrail: refuses an answer longer than limit characters."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.name = f"length_cap_{limit}"

    def check(self, text: str) -> tuple[bool, str]:
        if len(text) > self.limit:
            return False, f"{len(text)} characters, limit {self.limit}"
        return True, "ok"


class CardNumberGuard:
    """Output guardrail: refuses text that shows a payment card number (13 to 19 digits, with or
    without spaces or dashes between them)."""

    name = "card_numbers"
    PATTERN = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")

    def check(self, text: str) -> tuple[bool, str]:
        if self.PATTERN.search(text):
            return False, "shows a card number"
        return True, "ok"
