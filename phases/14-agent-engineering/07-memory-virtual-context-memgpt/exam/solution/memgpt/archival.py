"""Archival memory: the external, searchable store of facts."""
from __future__ import annotations

from dataclasses import dataclass

from .tokens import tokenize


@dataclass(frozen=True)
class ArchivalRecord:
    rid: str
    text: str
    tags: tuple[str, ...] = ()
    session_id: str = "s0"
    turn_id: int = 0


class ArchivalStore:
    """External context: unbounded and searchable, held in memory.

    Records get the ids a001, a002, ... in insertion order. Every record is kept, even when
    another record has the same text: each one cites its own session and turn.
    """

    def __init__(self) -> None:
        self._records: list[ArchivalRecord] = []
        self._counter = 0
        self._positions: dict[str, int] = {}
        self._terms: list[frozenset[str]] = []
        self._postings: dict[str, list[int]] = {}

    def insert(
        self, text: str, *, tags: tuple[str, ...] = (), session_id: str = "s0", turn_id: int = 0
    ) -> str:
        """Store one fact and return its new id."""
        self._counter += 1
        record = ArchivalRecord(f"a{self._counter:03d}", text, tuple(tags), session_id, turn_id)
        self._keep(record)
        return record.rid

    def _keep(self, record: ArchivalRecord) -> None:
        """Hold a stored record so that get, records and search see it."""
        position = len(self._records)
        self._records.append(record)
        self._positions[record.rid] = position
        terms = frozenset(tokenize(record.text))
        self._terms.append(terms)
        for term in terms:
            self._postings.setdefault(term, []).append(position)

    def get(self, rid: str) -> ArchivalRecord:
        """A stored record. Unknown ids raise KeyError."""
        return self._records[self._positions[rid]]

    def records(self) -> list[ArchivalRecord]:
        """Every record, in insertion order."""
        return list(self._records)

    def count(self) -> int:
        return len(self._records)

    def search(self, query: str, top_k: int = 3) -> list[tuple[float, ArchivalRecord]]:
        """Up to top_k (score, record) pairs, best first, for records that share a token with query.

        score is the Jaccard overlap of the distinct tokens (tokenize) of the query and the record:
        |q & r| / |q | r|. Records with the same score keep their insertion order.
        """
        query_terms = set(tokenize(query))
        shared: dict[int, int] = {}
        for term in query_terms:
            for position in self._postings.get(term, ()):
                shared[position] = shared.get(position, 0) + 1
        scored = [
            (overlap / (len(query_terms) + len(self._terms[position]) - overlap), position)
            for position, overlap in shared.items()
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [(score, self._records[position]) for score, position in scored[:top_k]]
