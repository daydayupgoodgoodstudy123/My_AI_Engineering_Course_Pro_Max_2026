"""Gateway guardrails: PII is redacted before a prompt leaves for any provider."""
from __future__ import annotations

import re

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{16}\b"),  # credit card
]


def redact_pii(text: str) -> tuple[str, bool]:
    """Replace every SSN- or card-shaped number with [REDACTED]; say whether anything changed."""
    redacted = False
    for pattern in PII_PATTERNS:
        text, hits = pattern.subn("[REDACTED]", text)
        redacted = redacted or hits > 0
    return text, redacted


def redact_messages(messages: list[dict]) -> tuple[list[dict], bool]:
    """Redact PII from the text of every message, whatever its role, before the request is sent.

    A message's content is a string, or None for an assistant message that only calls tools.
    Returns the messages to send, with every other field (tool_calls, tool_call_id, name) kept
    as it was, and whether anything was redacted.
    """
    prepared = []
    redacted = False
    for message in messages:
        copy = dict(message)
        if message.get("content") is not None:
            copy["content"], hit = redact_pii(message["content"])
            redacted = redacted or hit
        prepared.append(copy)
    return prepared, redacted
