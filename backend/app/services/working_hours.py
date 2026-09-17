"""Working hours of a school as intervals on the time line (ADR-014, T-16).

Downtime and «Нет соединения» count only inside working hours: a school computer switched off
for the night is not a broken line (plan.md §6, §16). Hours are local times of
``settings.timezone`` without an offset; everything they are compared with is UTC, so the local
day is built in that zone and then read as an absolute interval.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.schools import WorkingHours

# Order of ``Weekday`` of the API against ``date.weekday()`` (Monday is 0).
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# One interval of the time line, both ends aware datetimes, ``start`` before ``end``.
type Interval = tuple[datetime, datetime]


def working_windows(
    hours: WorkingHours, timezone: str, start: datetime, end: datetime
) -> list[Interval]:
    """Working hours of every local day between ``start`` and ``end``, clipped to that period."""
    zone = ZoneInfo(timezone)
    day = start.astimezone(zone).date()
    last = end.astimezone(zone).date()
    windows: list[Interval] = []
    while day <= last:
        if WEEKDAYS[day.weekday()] in hours.weekdays:
            opens = datetime.combine(day, hours.start, tzinfo=zone)
            closes = datetime.combine(day, hours.end, tzinfo=zone)
            if max(opens, start) < min(closes, end):
                windows.append((max(opens, start), min(closes, end)))
        day += timedelta(days=1)
    return windows


def is_working_time(hours: WorkingHours, timezone: str, moment: datetime) -> bool:
    """Whether ``moment`` falls inside the working hours of the school (ADR-014)."""
    local = moment.astimezone(ZoneInfo(timezone))
    return WEEKDAYS[local.weekday()] in hours.weekdays and hours.start <= local.time() < hours.end


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    """Overlapping and touching intervals joined into a sorted list of disjoint ones."""
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def intersect(first: list[Interval], second: list[Interval]) -> list[Interval]:
    """Parts of ``first`` covered by ``second``; both are expected merged."""
    return [
        (max(one_start, other_start), min(one_end, other_end))
        for one_start, one_end in first
        for other_start, other_end in second
        if max(one_start, other_start) < min(one_end, other_end)
    ]


def subtract(base: list[Interval], cut: list[Interval]) -> list[Interval]:
    """Parts of ``base`` left after removing ``cut``; both are expected merged."""
    rest: list[Interval] = []
    for start, end in base:
        left = start
        for cut_start, cut_end in cut:
            if cut_end <= left or cut_start >= end:
                continue
            if cut_start > left:
                rest.append((left, cut_start))
            left = cut_end
            if left >= end:
                break
        if left < end:
            rest.append((left, end))
    return rest


def duration_s(intervals: list[Interval]) -> float:
    """Total length of the intervals in seconds."""
    return sum((end - start).total_seconds() for start, end in intervals)
