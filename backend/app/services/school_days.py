"""Day strip of the school cabinet (T-61, DESIGN.md §3.27, docs/design/README.md §4.2).

One row per local day of ``settings.timezone``, oldest first, every day of the window present
even when nothing was measured on it: the strip of the cabinet has no gaps. A day is «Нет
соединения» when an outage of the school overlaps its working hours, otherwise it takes the
worst quality status of that day's measurements of the main lines without Wi-Fi (ADR-012),
otherwise «Нет данных» (ADR-004).

Downtime and the offline verdict are clipped to the working hours of the school, as the
availability of T-16 does: a line down while the school is closed is not a day without
internet (ADR-014). ``m_daily`` cannot answer this — it counts problems in one lumped column
and knows nothing about outages — so the day is folded from the raw measurements, one index
range per line, and the outages are intersected in Python with the helpers of
``working_hours`` (T-19, ``app/models/rollup.py``). Every query runs in the session of the
request, so RLS keeps the strip inside the user's scope (ADR-008).
"""

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, Measurement, Outage
from app.schemas.schools import SchoolDay, SchoolDays
from app.schemas.statuses import SchoolStatus
from app.services.school_card import ensure_school
from app.services.settings import system_settings
from app.services.status import SEVERITY, WIFI
from app.services.working_hours import (
    Interval,
    duration_s,
    intersect,
    merge,
    school_hours,
    working_windows,
)

# Statuses ``m_daily.problem_count`` counts: everything but «Норма» (ADR-004, T-19).
PROBLEM_STATUSES = frozenset(SEVERITY[1:])


def day_status(downtime_s: float, worst: int | None) -> SchoolStatus:
    """Status of one day: the outage first, then the worst measurement (§4.2)."""
    if downtime_s > 0:
        return "offline"
    return "no_data" if worst is None else SEVERITY[worst]


async def school_days(
    session: AsyncSession, school_id: int, *, days: int, period_to: datetime
) -> SchoolDays:
    """Status of every one of the last ``days`` local days of the school (ТЗ п. 13, ADR-004)."""
    await ensure_school(session, school_id)
    settings = await system_settings(session)
    zone = ZoneInfo(settings.timezone)
    # The strip answers in UTC whatever offset the request asked the end of the window in.
    period_to = period_to.astimezone(UTC)
    last_day = period_to.astimezone(zone).date()
    first_day = last_day - timedelta(days=days - 1)
    period_from = datetime.combine(first_day, time(), tzinfo=zone).astimezone(UTC)

    # Measurements the line is rated by: its main lines without Wi-Fi, as the school status and
    # the aggregates count them (ADR-012).
    counts: Counter[date] = Counter()
    problems: Counter[date] = Counter()
    worst: dict[date, int] = {}
    for measured_at, quality_status in await session.execute(
        select(Measurement.measured_at, Measurement.quality_status)
        .join(Line, Line.id == Measurement.line_id)
        .where(
            Line.school_id == school_id,
            Line.status == "main",
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.measured_at >= period_from,
            Measurement.measured_at < period_to,
        )
    ):
        day = measured_at.astimezone(zone).date()
        counts[day] += 1
        if quality_status is None:
            continue
        if quality_status in PROBLEM_STATUSES:
            problems[day] += 1
        worst[day] = max(worst.get(day, 0), SEVERITY.index(quality_status))

    # Outages of the school's lines, merged once and kept inside the working hours of the period.
    hours = (await school_hours(session, [school_id], settings))[school_id]
    windows = merge(working_windows(hours, settings.timezone, period_from, period_to))
    reported: list[Interval] = [
        (started_at, period_to if ended_at is None else ended_at)
        for started_at, ended_at in await session.execute(
            select(Outage.started_at, Outage.ended_at)
            .join(Line, Line.id == Outage.line_id)
            .where(
                Line.school_id == school_id,
                Outage.started_at < period_to,
                or_(Outage.ended_at.is_(None), Outage.ended_at > period_from),
            )
        )
    ]
    downtime = merge(intersect(windows, merge(reported)))

    strip = []
    for number in range(days):
        day = first_day + timedelta(days=number)
        opens = datetime.combine(day, time(), tzinfo=zone).astimezone(UTC)
        closes = datetime.combine(day + timedelta(days=1), time(), tzinfo=zone).astimezone(UTC)
        down_s = duration_s(intersect(downtime, [(opens, closes)]))
        strip.append(
            SchoolDay(
                date=day,
                status=day_status(down_s, worst.get(day)),
                measurements_count=counts[day],
                problem_count=problems[day],
                downtime_s=down_s,
            )
        )
    return SchoolDays(school_id=school_id, period_from=period_from, period_to=period_to, days=strip)
