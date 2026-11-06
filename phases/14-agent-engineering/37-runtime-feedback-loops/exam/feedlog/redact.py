"""Secret redaction. It runs before anything reaches a record: the file on disk is what leaks."""
from __future__ import annotations

import re

# (pattern, replacement), applied in this order. Audit them against the secret formats the
# runtime actually prints.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (
        re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|token)\s*[:=]\s*\S+"),
        r"\1=[REDACTED]",
    ),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA[REDACTED]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]+"), "xox-[REDACTED]"),
    (
        re.compile(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----"
        ),
        "[REDACTED PRIVATE KEY]",
    ),
]


def redact(text: str) -> tuple[str, int]:
    """Replace every secret the patterns find. Returns (text, number of secrets replaced).

    A private key is replaced as one block, from its BEGIN line through its END line.
    """
    hits = 0
    for pattern, replacement in PATTERNS:
        text, n = pattern.subn(replacement, text)
        hits += n
    return text, hits
