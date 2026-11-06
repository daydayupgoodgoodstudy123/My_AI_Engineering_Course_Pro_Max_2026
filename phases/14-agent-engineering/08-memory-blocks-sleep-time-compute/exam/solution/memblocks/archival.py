"""The archival tier: facts outside the prompt. Records are invalidated, never deleted."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArchivalRecord:
    rid: str
    text: str
    at: float = 0.0  # when the fact was stated, in seconds
    valid: bool = True
    reason: str = ""  # why it was invalidated


class Archival:
    """Archival memory. Invalid records stay, so an operator can see what the agent used to believe."""

    def __init__(self) -> None:
        self._records: list[ArchivalRecord] = []
        self._by_rid: dict[str, ArchivalRecord] = {}

    def insert(self, text: str, at: float = 0.0) -> str:
        """Store a record and return its id: a001, a002, ... in insertion order."""
        rid = f"a{len(self._records) + 1:03d}"
        record = ArchivalRecord(rid, text, at)
        self._records.append(record)
        self._by_rid[rid] = record
        return rid

    def get(self, rid: str) -> ArchivalRecord:
        """The record with this id, valid or not. Unknown ids raise KeyError."""
        return self._by_rid[rid]

    def invalidate(self, rid: str, reason: str) -> bool:
        """Mark a record invalid and say why. False if it already was; its first reason stays."""
        record = self.get(rid)
        if not record.valid:
            return False
        record.valid = False
        record.reason = reason
        return True

    def valid_records(self) -> list[ArchivalRecord]:
        return [r for r in self._records if r.valid]

    def all_records(self) -> list[ArchivalRecord]:
        """Every record in insertion order, invalid ones included."""
        return list(self._records)
