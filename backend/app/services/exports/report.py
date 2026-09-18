"""PDF report of a school over a period (T-32, ТЗ п. 9, plan.md §12): what the report shows.

The KPI are those of the analytics and of the aggregates export (T-27, T-31): the main line
without Wi-Fi, from ``m_daily``; the charts count the same measurements day by day. Downtime
comes from ``outages`` of the school's lines (T-16): overlapping reports of several computers are
one episode, cut to the period. The table lists every measurement of the school, as the raw
export does (T-30). Every query runs in the session of the request, so RLS keeps the report
inside the user's scope (ADR-008). The drawing is ``report_pdf.py``.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, Outage, Region, School
from app.schemas.exports import ExportCreate
from app.services.availability import school_availability
from app.services.exports.aggregates import aggregate_records
from app.services.exports.raw import raw_records
from app.services.status import WIFI
from app.services.working_hours import merge


@dataclass(frozen=True)
class Downtime:
    """One episode without connection; ``ongoing`` while it has not ended by the report."""

    started_at: datetime
    ended_at: datetime
    ongoing: bool

    @property
    def duration_s(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


@dataclass(frozen=True)
class ReportDay:
    """A local day of the charts: the mean download and the measurements by status."""

    day: date
    avg_download_mbps: float | None
    statuses: Counter[str]


@dataclass(frozen=True)
class SchoolReport:
    school_code: str
    school_name: str
    region_name: str
    address: str | None
    first_day: date
    last_day: date
    created_at: datetime
    timezone: str
    # The aggregates record of the school (T-31); None when it has no main line.
    kpis: dict[str, Any] | None
    availability_pct: float | None
    downtimes: list[Downtime]
    days: list[ReportDay]
    measurements: list[dict[str, Any]]

    @property
    def downtime_s(self) -> float:
        return sum(downtime.duration_s for downtime in self.downtimes)


async def school_downtimes(
    session: AsyncSession, school_id: int, *, start: datetime, end: datetime, now: datetime
) -> list[Downtime]:
    """Outages of the school's lines between ``start`` and ``end``, merged and cut to them."""
    intervals = []
    still_open = False
    for started_at, ended_at in await session.execute(
        select(Outage.started_at, Outage.ended_at)
        .join(Line, Line.id == Outage.line_id)
        .where(
            Line.school_id == school_id,
            Outage.started_at < end,
            or_(Outage.ended_at.is_(None), Outage.ended_at > start),
        )
    ):
        still_open = still_open or ended_at is None
        intervals.append((max(started_at, start), end if ended_at is None else min(ended_at, end)))
    return [
        Downtime(first, last, ongoing=still_open and last == end and end == now)
        for first, last in merge(intervals)
    ]


def report_days(
    measurements: list[dict[str, Any]], first_day: date, last_day: date
) -> list[ReportDay]:
    """Every day of the period, measured or not; the main line without Wi-Fi, as the KPI."""
    downloads: dict[str, list[float]] = defaultdict(list)
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    for record in measurements:
        if record["line_status"] != "main" or record["iface_type"] == WIFI:
            continue
        if record["download_mbps"] is not None:
            downloads[record["date"]].append(record["download_mbps"])
        if record["quality_status"] is not None:
            statuses[record["date"]][record["quality_status"]] += 1
    days = []
    day = first_day
    while day <= last_day:
        values = downloads.get(day.isoformat())
        days.append(
            ReportDay(
                day=day,
                avg_download_mbps=sum(values) / len(values) if values else None,
                statuses=statuses.get(day.isoformat(), Counter()),
            )
        )
        day += timedelta(days=1)
    return days


async def school_report(
    session: AsyncSession, body: ExportCreate, zone: tzinfo, timezone: str, *, now: datetime
) -> SchoolReport:
    """Everything the PDF of the one school of ``body`` shows; the school is already checked."""
    school_id = body.school_ids[0]
    school = (
        await session.execute(
            select(School.school_code, School.full_name, School.address, Region.name)
            .join(Region, Region.id == School.region_id)
            .where(School.id == school_id)
        )
    ).one()
    # What has not happened yet is neither downtime nor observed time.
    end = max(min(body.period_to, now), body.period_from)
    availability = await school_availability(session, school_id, start=body.period_from, end=end)
    kpis = await aggregate_records(session, body)
    measurements = await raw_records(session, body, zone)
    first_day = body.period_from.astimezone(zone).date()
    last_day = (body.period_to - timedelta(microseconds=1)).astimezone(zone).date()
    return SchoolReport(
        school_code=school.school_code,
        school_name=school.full_name,
        region_name=school.name,
        address=school.address,
        first_day=first_day,
        last_day=last_day,
        created_at=now.astimezone(zone),
        timezone=timezone,
        kpis=kpis[0] if kpis else None,
        availability_pct=availability.uptime_pct,
        downtimes=await school_downtimes(
            session, school_id, start=body.period_from, end=end, now=now
        ),
        days=report_days(measurements, first_day, last_day),
        measurements=measurements,
    )
