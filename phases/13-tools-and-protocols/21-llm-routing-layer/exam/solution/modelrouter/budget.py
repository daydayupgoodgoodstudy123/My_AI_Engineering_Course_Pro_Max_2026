"""Monthly spend caps per team (one API key per team)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone


def month_of(at: datetime) -> str:
    """The calendar month, in UTC, that a moment falls in, written YYYY-MM."""
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError(f"need a timezone-aware time, got {at!r}")
    return at.astimezone(timezone.utc).strftime("%Y-%m")


class BudgetExceeded(Exception):
    """The team has used up its cap for this month."""

    def __init__(self, team: str, month: str, cap: int) -> None:
        super().__init__(f"team {team} has used its {month} budget of {cap} micro-dollars")
        self.team = team
        self.month = month
        self.cap = cap


class Budget:
    """Monthly spend caps per team, in micro-dollars.

    Months are calendar months in UTC. A team may send a request while its spend for the
    month the request arrives in is below its cap; that request is served and charged in full
    even if it takes the team past the cap, and the next one is refused. A team without a cap
    is never refused. Spend in one month never counts against another.
    """

    def __init__(self, caps: dict[str, int]) -> None:
        self.caps = dict(caps)
        self._spent: defaultdict[tuple[str, str], int] = defaultdict(int)

    def spent(self, team: str, month: str) -> int:
        """Micro-dollars charged to the team in a month, written YYYY-MM."""
        return self._spent.get((team, month), 0)

    def check(self, team: str, at: datetime) -> None:
        """Raise BudgetExceeded if the team has used up its cap for the month of at."""
        cap = self.caps.get(team)
        if cap is None:
            return
        month = month_of(at)
        if self.spent(team, month) >= cap:
            raise BudgetExceeded(team, month, cap)

    def charge(self, team: str, at: datetime, micros: int) -> None:
        """Add a served request's cost to the team's spend for the month of at."""
        self._spent[(team, month_of(at))] += micros
