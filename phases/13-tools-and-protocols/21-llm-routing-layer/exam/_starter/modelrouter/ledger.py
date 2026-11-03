"""The cost ledger: every routed call, one row each, in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from .providers import Attempt


@dataclass(frozen=True)
class Call:
    """One routed call, as the ledger keeps it."""

    team: str
    alias: str
    at: datetime  # timezone-aware
    attempts: tuple[Attempt, ...]  # in the order they were made
    served_model: str | None  # None when no model served the call
    input_tokens: int
    output_tokens: int
    cost_micros: int


class TeamMonth(NamedTuple):
    """One team's calls in one month."""

    team: str
    calls: int
    failed: int  # calls that no model served
    input_tokens: int
    output_tokens: int
    cost_micros: int


class Ledger:
    """Routed calls and what they cost, one row per call, kept in SQLite.

    Costs are whole micro-dollars (int, as cost_micros computes them), and every total is the
    exact sum of the calls it covers. Months are calendar months in UTC, written YYYY-MM: the
    months month_of gives and the budget enforces.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def record(self, call: Call) -> int:
        """Store one call and return its number: 1 for the ledger's first call, then 2, 3, ...

        A cost that is not an int raises TypeError.
        """
        raise NotImplementedError

    def get(self, number: int) -> Call:
        """The call with that number. Unknown numbers raise KeyError."""
        raise NotImplementedError

    def calls(self, team: str | None = None, month: str | None = None) -> list[Call]:
        """Recorded calls in the order they were recorded, optionally for one team or one month."""
        raise NotImplementedError

    def spend(self, team: str, month: str) -> int:
        """The team's total cost in a month, in micro-dollars: 0 if it made no calls."""
        raise NotImplementedError

    def report(self, month: str) -> list[TeamMonth]:
        """One row per team that made calls in the month, ordered by team name."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
