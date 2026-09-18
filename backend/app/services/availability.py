"""Availability of a school: 1 − downtime / observed working time (ТЗ п. 11, plan.md §6).

Observed time is the working hours of the school inside the period (ADR-014). Downtime is what
the agents reported in ``outages`` plus the gaps in their heartbeat: a heartbeat vouches for the
next ``offline_after_s``, and silence longer than that is «Нет соединения» (T-16, ADR-004).
Devices of one school vouch for each other: while any of them answers, the school is on line.

Analytics asks for hundreds of schools over a month at once (T-27), so heartbeats never leave
the database one by one: it folds them into the stretches they cover, a handful per school a day.
"""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Heartbeat, MonitoringPoint, Outage
from app.schemas.schools import WorkingHours
from app.services.settings import system_settings
from app.services.working_hours import (
    Interval,
    duration_s,
    intersect,
    merge,
    subtract,
    working_windows,
)


@dataclass(frozen=True)
class Availability:
    """Availability of a school over a period; ``uptime_pct`` is empty when nothing was observed."""

    uptime_pct: float | None
    observed_s: float
    downtime_s: float


async def school_availability(
    session: AsyncSession, school_id: int, *, start: datetime, end: datetime
) -> Availability:
    """Availability of the school between ``start`` and ``end`` (ТЗ п. 11).

    A school with neither heartbeats nor outages in the period was not observed at all, so it
    gets no number instead of a zero: «нет данных» is not «лежало».
    """
    return (await schools_availability(session, [school_id], start=start, end=end))[school_id]


async def schools_availability(
    session: AsyncSession, school_ids: Collection[int], *, start: datetime, end: datetime
) -> dict[int, Availability]:
    """Availability of every school of ``school_ids``, in two queries whatever their number."""
    settings = await system_settings(session)
    hours = WorkingHours.model_validate(settings.default_working_hours)
    windows = merge(working_windows(hours, settings.timezone, start, end))
    observed_s = duration_s(windows)
    silence = timedelta(seconds=settings.offline_after_s)
    if not school_ids:
        return {}

    # A stretch starts at a heartbeat that comes more than ``silence`` after the previous one of
    # the same school; it is covered from its first heartbeat to ``silence`` after its last.
    beats = (
        select(
            MonitoringPoint.school_id,
            Heartbeat.ts,
            (
                Heartbeat.ts
                - func.lag(Heartbeat.ts).over(
                    partition_by=MonitoringPoint.school_id, order_by=Heartbeat.ts
                )
            ).label("gap"),
        )
        .join(Device, Device.id == Heartbeat.device_id)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(
            MonitoringPoint.school_id.in_(school_ids),
            Heartbeat.online,
            # A heartbeat just before the period still vouches for its first minutes.
            Heartbeat.ts > start - silence,
            Heartbeat.ts <= end,
        )
        .subquery()
    )
    numbered = select(
        beats.c.school_id,
        beats.c.ts,
        func.sum(case((or_(beats.c.gap.is_(None), beats.c.gap > silence), 1), else_=0))
        .over(partition_by=beats.c.school_id, order_by=beats.c.ts)
        .label("stretch"),
    ).subquery()
    covered: dict[int, list[Interval]] = defaultdict(list)
    for school_id, first, last in await session.execute(
        select(numbered.c.school_id, func.min(numbered.c.ts), func.max(numbered.c.ts)).group_by(
            numbered.c.school_id, numbered.c.stretch
        )
    ):
        covered[school_id].append((first, last + silence))

    reported: dict[int, list[Interval]] = defaultdict(list)
    for school_id, started_at, ended_at in await session.execute(
        select(MonitoringPoint.school_id, Outage.started_at, Outage.ended_at)
        .join(Device, Device.id == Outage.device_id)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(
            MonitoringPoint.school_id.in_(school_ids),
            Outage.started_at < end,
            or_(Outage.ended_at.is_(None), Outage.ended_at > start),
        )
    ):
        reported[school_id].append((started_at, end if ended_at is None else ended_at))

    result: dict[int, Availability] = {}
    for school_id in school_ids:
        if not observed_s or (school_id not in covered and school_id not in reported):
            result[school_id] = Availability(uptime_pct=None, observed_s=observed_s, downtime_s=0)
            continue
        # Working time no heartbeat vouches for, plus the outages the agents reported themselves.
        downtime_s = duration_s(
            merge(
                subtract(windows, merge(covered[school_id]))
                + intersect(windows, merge(reported[school_id]))
            )
        )
        result[school_id] = Availability(
            uptime_pct=100 * (1 - downtime_s / observed_s),
            observed_s=observed_s,
            downtime_s=downtime_s,
        )
    return result
