"""Cron-shaped schedules: parse five-field expressions and work out when they fire, in UTC."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

UTC = timezone.utc

# (name, lowest, highest) for minute, hour, day of month, month, day of week
FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day of month", 1, 31),
    ("month", 1, 12),
    ("day of week", 0, 7),
)


@dataclass(frozen=True)
class Cron:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]  # days of the month, 1-31
    months: frozenset[int]  # 1-12
    weekdays: frozenset[int]  # 0-6, Sunday is 0
    days_restricted: bool  # the day-of-month field is not "*"
    weekdays_restricted: bool  # the day-of-week field is not "*"


def parse_cron(expr: str) -> Cron:
    """Parse "minute hour day-of-month month day-of-week", fields separated by whitespace.

    Each field is a comma-separated list of: *, a number, a range a-b, or a step over *
    or over a range (*/15, 10-50/20). A step counts from the start of its range, so */10
    in the day-of-month field means 1, 11, 21, 31. Day of week runs 0-7, where 0 and 7
    are both Sunday. Anything else raises ValueError.
    """
    raise NotImplementedError


def next_fire(cron: Cron | str, after: datetime) -> datetime:
    """The first minute strictly after `after` at which the schedule fires, as an aware UTC datetime.

    The schedule runs on UTC; `after` must be timezone-aware (ValueError otherwise) and may
    be in any zone. A day matches when its month matches and, if both day fields are
    restricted (neither is *), either day field matches; otherwise both must (a * field
    matches every day). A schedule that can never fire, such as 30 February, raises ValueError.
    """
    raise NotImplementedError


def missed(
    cron: Cron | str, last_fire: datetime, now: datetime, catch_up: str
) -> tuple[list[datetime], int]:
    """Plan a scheduler tick, maybe after downtime: which fires in (last_fire, now] to run.

    last_fire is the last fire already handled; a fire exactly at now is due. With
    catch_up="latest" only the most recent due fire runs. With catch_up="skip" a fire runs
    only if it falls in the same minute as now. Returns (fires to run, number skipped).
    """
    raise NotImplementedError
