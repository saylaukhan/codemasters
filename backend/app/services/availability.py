"""Availability of a school: 1 − downtime / observed working time (ТЗ п. 11, plan.md §6).

Observed time is the working hours of the school inside the period (ADR-014). Downtime is what
the agents reported in ``outages`` plus the gaps in their heartbeat: a heartbeat vouches for the
next ``offline_after_s``, and silence longer than that is «Нет соединения» (T-16, ADR-004).
Devices of one school vouch for each other: while any of them answers, the school is on line.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Heartbeat, MonitoringPoint, Outage
from app.schemas.schools import WorkingHours
from app.services.settings import system_settings
from app.services.working_hours import (
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
    settings = await system_settings(session)
    hours = WorkingHours.model_validate(settings.default_working_hours)
    windows = merge(working_windows(hours, settings.timezone, start, end))
    observed_s = duration_s(windows)
    silence = timedelta(seconds=settings.offline_after_s)

    beats = (
        await session.scalars(
            select(Heartbeat.ts)
            .join(Device, Device.id == Heartbeat.device_id)
            .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
            .where(
                MonitoringPoint.school_id == school_id,
                Heartbeat.online,
                # A heartbeat just before the period still vouches for its first minutes.
                Heartbeat.ts > start - silence,
                Heartbeat.ts <= end,
            )
        )
    ).all()
    outages = (
        (
            await session.execute(
                select(Outage.started_at, Outage.ended_at)
                .join(Device, Device.id == Outage.device_id)
                .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
                .where(
                    MonitoringPoint.school_id == school_id,
                    Outage.started_at < end,
                    or_(Outage.ended_at.is_(None), Outage.ended_at > start),
                )
            )
        )
        .tuples()
        .all()
    )
    if not observed_s or (not beats and not outages):
        return Availability(uptime_pct=None, observed_s=observed_s, downtime_s=0)

    covered = merge((beat, beat + silence) for beat in beats)
    reported = merge(
        (started_at, end if ended_at is None else ended_at) for started_at, ended_at in outages
    )
    # Working time no heartbeat vouches for, plus the outages the agents reported themselves.
    downtime_s = duration_s(merge(subtract(windows, covered) + intersect(windows, reported)))
    return Availability(
        uptime_pct=100 * (1 - downtime_s / observed_s),
        observed_s=observed_s,
        downtime_s=downtime_s,
    )
