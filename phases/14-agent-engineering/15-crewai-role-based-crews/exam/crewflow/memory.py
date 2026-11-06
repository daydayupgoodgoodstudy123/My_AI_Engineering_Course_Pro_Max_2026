"""Short-term and long-term crew memory, with a hashed stand-in for an embeddings provider."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

WORD = re.compile(r"\w+")


def embed(text: str, dim: int) -> list[float]:
    """A unit vector for text: every word is hashed to one of dim slots with a sign (feature hashing).

    It stands in for a real embeddings provider: texts that share words point the same way.
    """
    vector = [0.0] * dim
    for word in WORD.findall(text.lower()):
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:4], "little") % dim] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


class Memory:
    """Short-term and long-term memory for a crew, two of CrewAI's four memory types.

    short_term is the current run's buffer of (role, output). Long-term memory survives
    across kickoffs and is searched by similarity to a query. Each long-term record is
    embedded once, not again on every recall.
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self.short_term: list[tuple[str, Any]] = []
        self._long_term: list[tuple[str, str]] = []

    def reset_short_term(self) -> None:
        self.short_term = []

    def write_short_term(self, role: str, value: Any) -> None:
        self.short_term.append((role, value))

    def write_long_term(self, role: str, text: str) -> None:
        self._long_term.append((role, text))

    def recall_long_term(self, query: str, k: int = 2) -> list[tuple[str, str, float]]:
        """The k long-term records most similar to query, as (role, text, score), best first.

        score is the dot product of the two unit vectors; equal scores keep write order.
        """
        q = embed(query, self.dim)
        scored = [(role, text, _dot(q, embed(text, self.dim))) for role, text in self._long_term]
        scored.sort(key=lambda row: row[2], reverse=True)
        return scored[:k]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
