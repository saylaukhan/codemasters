"""Календарь: когда данные школы ничего не говорят о линии (T-70, docs/design/README.md §6.5).

Каникулы и праздник — целые местные сутки, в которые школа не работает: замеры принимаются и
хранятся, но доступность не считается, инциденты не создаются, а тишина агента показывается как
«Нет данных · каникулы», а не «Нет соединения». Плановые работы — окно одного поставщика: по его
линиям инциденты в это время не заводятся и окно не входит в его оценку (ТЗ п. 14).

The bulk form is the one the wirings use: availability asks for hundreds of schools over a month
(T-27), detection for one line per run (T-40), and the single moment of ``is_quiet`` is that same
answer asked for one school. Intervals are handed to the helpers of ``working_hours.py``, so the
calendar is subtracted by the same code that subtracts downtime.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models import CalendarEvent, School
from app.schemas.calendar import CalendarKind
from app.services.working_hours import Interval, merge

PLANNED_WORKS = "planned_works"


@dataclass(frozen=True)
class QuietPeriod:
    """One event of the calendar as the calculations see it; ``provider_id`` — planned works."""

    kind: CalendarKind
    provider_id: int | None
    start: datetime
    end: datetime


async def quiet_periods(
    session: AsyncSession, school_ids: Collection[int], *, start: datetime, end: datetime
) -> dict[int, list[QuietPeriod]]:
    """Events of the calendar of every school of ``school_ids`` that touch ``start``…``end``.

    An event of the oblast reaches every school, an event of a district the schools of that
    district, an event of a school that school alone; two queries whatever the number of schools.
    """
    found: dict[int, list[QuietPeriod]] = {school_id: [] for school_id in school_ids}
    if not school_ids:
        return found
    regions: dict[int, int] = {
        school_id: region_id
        for school_id, region_id in await session.execute(
            select(School.id, School.region_id).where(School.id.in_(school_ids))
        )
    }
    events = list(
        await session.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.starts_at <= end,
                CalendarEvent.ends_at > start,
                or_(
                    CalendarEvent.scope == "oblast",
                    CalendarEvent.region_id.in_(set(regions.values())),
                    CalendarEvent.school_id.in_(school_ids),
                ),
            )
            .order_by(CalendarEvent.starts_at, CalendarEvent.id)
        )
    )
    for school_id in school_ids:
        region_id = regions.get(school_id)
        for event in events:
            covers_school = (
                event.scope == "oblast"
                or (event.scope == "district" and event.region_id == region_id)
                or (event.scope == "school" and event.school_id == school_id)
            )
            if covers_school:
                found[school_id].append(
                    QuietPeriod(
                        kind=cast(CalendarKind, event.kind),
                        provider_id=event.provider_id,
                        start=event.starts_at,
                        end=event.ends_at,
                    )
                )
    return found


def school_windows(periods: Iterable[QuietPeriod]) -> list[Interval]:
    """Quiet time of the school itself: the works of one provider do not close its doors."""
    return merge((period.start, period.end) for period in periods if period.provider_id is None)


def line_windows(periods: Iterable[QuietPeriod], provider_id: int | None) -> list[Interval]:
    """Quiet time of one line: the days of the school plus the works of its own provider."""
    return merge(
        (period.start, period.end)
        for period in periods
        if period.provider_id is None or period.provider_id == provider_id
    )


def covers(windows: Iterable[Interval], moment: datetime) -> bool:
    """Whether ``moment`` falls inside one of the intervals."""
    return any(start <= moment < end for start, end in windows)


async def quiet_schools(
    session: AsyncSession, school_ids: Collection[int], *, now: datetime
) -> dict[int, CalendarKind]:
    """Schools of ``school_ids`` that are quiet at ``now``, each with the kind of its event.

    The kind travels with the status so the panel prints «Нет данных · каникулы» through the
    hint of the device table instead of a second rule of its own (DESIGN.md §4.1).
    """
    periods = await quiet_periods(session, school_ids, start=now, end=now)
    quiet: dict[int, CalendarKind] = {}
    for school_id, found in periods.items():
        covering = [
            period
            for period in found
            if period.provider_id is None and period.start <= now < period.end
        ]
        if covering:
            quiet[school_id] = covering[0].kind
    return quiet


async def is_quiet(session: AsyncSession, school_id: int, at: datetime) -> CalendarKind | None:
    """Kind of the event that keeps the school quiet at ``at``; None — an ordinary moment."""
    return (await quiet_schools(session, [school_id], now=at)).get(school_id)


def outside_planned_works(
    provider_id: InstrumentedAttribute[int] | InstrumentedAttribute[int | None],
    moment: InstrumentedAttribute[datetime],
) -> ColumnElement[bool]:
    """SQL condition: ``moment`` is not inside a planned-works window of ``provider_id``.

    The score of a provider counts what happened outside the windows it announced (ТЗ п. 14):
    the condition is added to the queries of ``provider_score.py`` instead of loading the
    windows into Python.
    """
    return ~(
        select(CalendarEvent.id)
        .where(
            CalendarEvent.kind == PLANNED_WORKS,
            CalendarEvent.provider_id == provider_id,
            CalendarEvent.starts_at <= moment,
            CalendarEvent.ends_at > moment,
        )
        .exists()
    )
