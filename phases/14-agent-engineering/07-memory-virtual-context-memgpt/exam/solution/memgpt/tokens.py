"""Token estimates for the context budget, and the tokenizer archival search uses."""
from __future__ import annotations

import math


def approx_tokens(text: str) -> int:
    """Estimated token count of one text: ceil(len(text.split()) * 1.3). An empty text costs 0."""
    return math.ceil(len(text.split()) * 1.3)


def tokenize(text: str) -> list[str]:
    """Search terms of a text: lowercased and split on whitespace. Punctuation stays attached."""
    return text.lower().split()
