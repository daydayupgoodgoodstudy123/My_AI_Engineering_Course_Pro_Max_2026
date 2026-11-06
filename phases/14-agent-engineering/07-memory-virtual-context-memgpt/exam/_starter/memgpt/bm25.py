"""Okapi BM25 over archival records, and recall@k to compare it with token overlap."""
from __future__ import annotations

from collections.abc import Callable, Iterable

from .archival import ArchivalRecord

Search = Callable[[str, int], list[tuple[float, ArchivalRecord]]]


class BM25:
    """Okapi BM25 over a fixed list of archival records, tokenized with tokens.tokenize().

    score(q, d) = sum over the tokens t of q of
        idf(t) * tf(t, d) * (k1 + 1) / (tf(t, d) + k1 * (1 - b + b * len(d) / avgdl))
    The sum runs over the query's tokens as written, so a token that appears twice in the query
    counts twice.

    idf(t) = ln(1 + (N - n(t) + 0.5) / (n(t) + 0.5)), which is never negative.
    tf(t, d) is how often t occurs in d, n(t) how many records contain t, N how many records
    there are, len(d) how many tokens d has, and avgdl the mean len(d) over all N records.
    Every record counts towards N and avgdl, empty ones included.
    """

    def __init__(self, records: Iterable[ArchivalRecord], k1: float = 1.2, b: float = 0.75) -> None:
        self.records = list(records)
        self.k1 = k1
        self.b = b

    def search(self, query: str, top_k: int = 10) -> list[tuple[float, ArchivalRecord]]:
        """Up to top_k (score, record) pairs with a positive score, best first.

        Records with the same score keep their order in the list BM25 was built from.
        """
        raise NotImplementedError


def recall_at_k(search: Search, cases: list[tuple[str, set[str]]], k: int) -> float:
    """Mean recall@k of a search function over (query, relevant rids) cases.

    A case's recall@k is the fraction of its relevant rids among the first k results of
    search(query, k). Every case counts in the mean, including one with no results at all.
    A case with no relevant rids, or an empty list of cases, raises ValueError.
    """
    raise NotImplementedError
