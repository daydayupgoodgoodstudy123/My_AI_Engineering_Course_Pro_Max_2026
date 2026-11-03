"""The cost ledger: every routed call, one row each, in SQLite."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NamedTuple

from .budget import month_of
from .providers import Attempt

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    alias TEXT NOT NULL,
    at TEXT NOT NULL,
    month TEXT NOT NULL,
    attempts TEXT NOT NULL,
    served_model TEXT,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_micros INTEGER NOT NULL
)
"""

COLUMNS = "team, alias, at, attempts, served_model, input_tokens, output_tokens, cost_micros"


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
        with self._db:
            self._db.execute(SCHEMA)

    def record(self, call: Call) -> int:
        """Store one call and return its number: 1 for the ledger's first call, then 2, 3, ...

        A cost that is not an int raises TypeError.
        """
        if type(call.cost_micros) is not int:
            raise TypeError(f"cost_micros must be an int number of micro-dollars, got {call.cost_micros!r}")
        month = month_of(call.at)
        at = call.at.astimezone(timezone.utc).isoformat(timespec="microseconds")
        attempts = json.dumps([[a.model, a.status] for a in call.attempts])
        with self._db:
            cursor = self._db.execute(
                f"INSERT INTO calls ({COLUMNS}, month) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (call.team, call.alias, at, attempts, call.served_model,
                 call.input_tokens, call.output_tokens, call.cost_micros, month),
            )
        return cursor.lastrowid

    def get(self, number: int) -> Call:
        """The call with that number. Unknown numbers raise KeyError."""
        row = self._db.execute(f"SELECT {COLUMNS} FROM calls WHERE number = ?", (number,)).fetchone()
        if row is None:
            raise KeyError(number)
        return _to_call(row)

    def calls(self, team: str | None = None, month: str | None = None) -> list[Call]:
        """Recorded calls in the order they were recorded, optionally for one team or one month."""
        where, params = [], []
        if team is not None:
            where.append("team = ?")
            params.append(team)
        if month is not None:
            where.append("month = ?")
            params.append(month)
        query = f"SELECT {COLUMNS} FROM calls"
        if where:
            query += " WHERE " + " AND ".join(where)
        return [_to_call(row) for row in self._db.execute(query + " ORDER BY number", params)]

    def spend(self, team: str, month: str) -> int:
        """The team's total cost in a month, in micro-dollars: 0 if it made no calls."""
        (total,) = self._db.execute(
            "SELECT COALESCE(SUM(cost_micros), 0) FROM calls WHERE team = ? AND month = ?",
            (team, month),
        ).fetchone()
        return total

    def report(self, month: str) -> list[TeamMonth]:
        """One row per team that made calls in the month, ordered by team name."""
        rows = self._db.execute(
            "SELECT team, COUNT(*), COUNT(*) - COUNT(served_model),"
            " SUM(input_tokens), SUM(output_tokens), SUM(cost_micros)"
            " FROM calls WHERE month = ? GROUP BY team ORDER BY team",
            (month,),
        )
        return [TeamMonth(*row) for row in rows]

    def close(self) -> None:
        self._db.close()


def _to_call(row: tuple) -> Call:
    team, alias, at, attempts, served_model, input_tokens, output_tokens, cost = row
    return Call(
        team=team,
        alias=alias,
        at=datetime.fromisoformat(at),
        attempts=tuple(Attempt(model, status) for model, status in json.loads(attempts)),
        served_model=served_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_micros=cost,
    )
