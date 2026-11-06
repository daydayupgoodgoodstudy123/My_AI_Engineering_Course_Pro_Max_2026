"""Cron-shaped schedules: parse five-field expressions and work out when they fire, in UTC."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc

# (name, lowest, highest) for minute, hour, day of month, month, day of week
FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day of month", 1, 31),
    ("month", 1, 12),
    ("day of week", 0, 7),
)

# the most days each month can have (February in a leap year)
MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


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
    parts = expr.split()
    if len(parts) != len(FIELDS):
        raise ValueError(f"a cron expression has 5 fields, got {len(parts)}: {expr!r}")
    values = [_parse_field(text, *spec) for text, spec in zip(parts, FIELDS)]
    minutes, hours, days, months, weekdays = values
    return Cron(
        minutes=minutes,
        hours=hours,
        days=days,
        months=months,
        weekdays=frozenset(d % 7 for d in weekdays),
        days_restricted=parts[2] != "*",
        weekdays_restricted=parts[4] != "*",
    )


def next_fire(cron: Cron | str, after: datetime) -> datetime:
    """The first minute strictly after `after` at which the schedule fires, as an aware UTC datetime.

    The schedule runs on UTC; `after` must be timezone-aware (ValueError otherwise) and may
    be in any zone. A day matches when its month matches and, if both day fields are
    restricted (neither is *), either day field matches; otherwise both must (a * field
    matches every day). A schedule that can never fire, such as 30 February, raises ValueError.
    """
    if isinstance(cron, str):
        cron = parse_cron(cron)
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("after must be timezone-aware")
    if not _can_fire(cron):
        raise ValueError("this schedule never fires")
    start = after.astimezone(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
    day, earliest = start.date(), (start.hour, start.minute)
    while True:
        if day.month not in cron.months:
            day = date(day.year + day.month // 12, day.month % 12 + 1, 1)
            earliest = (0, 0)
            continue
        if _day_matches(cron, day):
            found = _first_time(cron, earliest)
            if found is not None:
                return datetime(day.year, day.month, day.day, found[0], found[1], tzinfo=UTC)
        day += timedelta(days=1)
        earliest = (0, 0)


def missed(
    cron: Cron | str, last_fire: datetime, now: datetime, catch_up: str
) -> tuple[list[datetime], int]:
    """Plan a scheduler tick, maybe after downtime: which fires in (last_fire, now] to run.

    last_fire is the last fire already handled; a fire exactly at now is due. With
    catch_up="latest" only the most recent due fire runs. With catch_up="skip" a fire runs
    only if it falls in the same minute as now. Returns (fires to run, number skipped).
    """
    if catch_up not in ("latest", "skip"):
        raise ValueError(f"catch_up is 'latest' or 'skip', got {catch_up!r}")
    if isinstance(cron, str):
        cron = parse_cron(cron)
    due: list[datetime] = []
    fire = next_fire(cron, last_fire)
    while fire <= now:
        due.append(fire)
        fire = next_fire(cron, fire)
    if not due:
        return [], 0
    if catch_up == "latest":
        return [due[-1]], len(due) - 1
    this_minute = now.astimezone(UTC).replace(second=0, microsecond=0)
    run = [due[-1]] if due[-1] == this_minute else []
    return run, len(due) - len(run)


def _parse_field(text: str, name: str, low: int, high: int) -> frozenset[int]:
    values: set[int] = set()
    for item in text.split(","):
        span, slash, step_text = item.partition("/")
        if span == "*":
            start, end = low, high
        elif "-" in span:
            first, _, last = span.partition("-")
            start, end = _number(first, name, low, high), _number(last, name, low, high)
            if start > end:
                raise ValueError(f"{name}: range {span!r} runs backwards")
        elif slash:
            raise ValueError(f"{name}: a step needs * or a range, got {item!r}")
        else:
            start = end = _number(span, name, low, high)
        step = 1
        if slash:
            if not re.fullmatch(r"[0-9]+", step_text) or int(step_text) == 0:
                raise ValueError(f"{name}: bad step in {item!r}")
            step = int(step_text)
        values.update(range(start, end + 1, step))
    return frozenset(values)


def _number(text: str, name: str, low: int, high: int) -> int:
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError(f"{name}: {text!r} is not a number")
    value = int(text)
    if not low <= value <= high:
        raise ValueError(f"{name}: {value} is outside {low}-{high}")
    return value


def _can_fire(cron: Cron) -> bool:
    if cron.days_restricted and not cron.weekdays_restricted:
        return any(day <= MONTH_DAYS[month - 1] for month in cron.months for day in cron.days)
    return True


def _day_matches(cron: Cron, day: date) -> bool:
    in_month = day.day in cron.days
    in_week = (day.weekday() + 1) % 7 in cron.weekdays  # Python: Monday is 0; cron: Sunday is 0
    if cron.days_restricted and cron.weekdays_restricted:
        return in_month or in_week
    return in_month and in_week


def _first_time(cron: Cron, earliest: tuple[int, int]) -> tuple[int, int] | None:
    for hour in sorted(cron.hours):
        if hour < earliest[0]:
            continue
        for minute in sorted(cron.minutes):
            if (hour, minute) >= earliest:
                return hour, minute
    return None
