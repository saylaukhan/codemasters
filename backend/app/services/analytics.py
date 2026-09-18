"""Analytics of the panel (T-27, ТЗ п. 5, п. 13): rows of a level, time series and heatmap.

Numbers come from the continuous aggregates (T-19), never from raw measurements: ``m_hourly``
for the series of a day and the heatmap, ``m_daily`` for the series of a week or a month. The
aggregates have no RLS of their own (the view reads ``measurements`` as its owner), so every
query here reaches them only through ``lines``, where RLS keeps the user's scope (ADR-008).
Averages of buckets are weighted by the number of measurements: the mean of means is wrong.
Hours and days are local ones of ``settings.timezone`` (ADR-014).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.exceptions import RequestValidationError
from sqlalchemy import ColumnElement, Select, case, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import Line, MDaily, MHourly, Provider, Region, School
from app.schemas.analytics import (
    AnalyticsGranularity,
    AnalyticsHeatmapCell,
    AnalyticsLevel,
    AnalyticsPeriod,
    AnalyticsReport,
    AnalyticsRow,
    AnalyticsSeriesPoint,
    MetricStats,
)
from app.schemas.statuses import LineStatus
from app.schemas.thresholds import ThresholdValues
from app.services.availability import schools_availability
from app.services.settings import NOT_CONFIGURED, NOT_CONFIGURED_DETAIL, system_settings
from app.services.thresholds import threshold_profile
from app.services.working_hours import WEEKDAYS

# Days before today that a preset reaches back: «неделя» and «месяц» include today.
PRESET_DAYS: dict[AnalyticsPeriod, int] = {"today": 0, "week": 6, "month": 29}

BUCKET_WIDTH: dict[AnalyticsGranularity, timedelta] = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
}

METRICS = ("download_mbps", "upload_mbps", "ping_ms")


@dataclass(frozen=True)
class AnalyticsFilters:
    school_id: int | None = None
    region_id: int | None = None
    provider_id: int | None = None
    connection_type_id: int | None = None
    line_status: LineStatus = "main"


def invalid_period(field: str, message: str) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("query", field),
                "msg": message,
                "ctx": {"error": message},
            }
        ]
    )


def period_bounds(
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    *,
    now: datetime,
    timezone: str,
) -> tuple[datetime, datetime]:
    """Start and end of the period: a preset counts whole local days up to ``now``."""
    if period == "custom":
        if period_from is None or period_to is None:
            field = "period_from" if period_from is None else "period_to"
            raise invalid_period(field, "При period=custom нужны period_from и period_to")
        if period_to <= period_from:
            raise invalid_period("period_to", "period_to должен быть позже period_from")
        return period_from, period_to
    if period_from is not None or period_to is not None:
        field = "period_from" if period_from is not None else "period_to"
        raise invalid_period(field, "period_from и period_to задаются только при period=custom")
    zone = ZoneInfo(timezone)
    first_day = now.astimezone(zone).date() - timedelta(days=PRESET_DAYS[period])
    return datetime.combine(first_day, time(), tzinfo=zone).astimezone(UTC), now


def weighted(column: Any, count: Any) -> Any:
    """Average of bucket averages weighted by their measurements; empty buckets do not count."""
    counted = func.sum(case((column.is_not(None), count), else_=0))
    return func.sum(column * count) / func.nullif(counted, 0)


def percent(part: int, whole: int) -> float | None:
    return 100 * part / whole if whole else None


def stats(row: Any, metric: str) -> MetricStats | None:
    avg = getattr(row, f"avg_{metric}")
    if avg is None:
        return None
    return MetricStats(
        avg=float(avg),
        min=float(getattr(row, f"min_{metric}")),
        max=float(getattr(row, f"max_{metric}")),
    )


async def analytics_report(
    session: AsyncSession,
    level: AnalyticsLevel,
    filters: AnalyticsFilters,
    *,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    now: datetime,
) -> AnalyticsReport:
    settings = await system_settings(session)
    start, end = period_bounds(period, period_from, period_to, now=now, timezone=settings.timezone)
    granularity: AnalyticsGranularity = "hour" if period == "today" else "day"
    rollup: Any = MHourly if granularity == "hour" else MDaily

    # Lines of the selection, visible to the user: RLS on ``lines`` and ``schools`` applies.
    query = (
        select(
            Line.id.label("line_id"),
            Line.school_id,
            Line.provider_id,
            School.region_id,
            or_(Line.contract_down_mbps.is_not(None), Line.contract_up_mbps.is_not(None)).label(
                "has_contract"
            ),
            Line.compliance_sustained_mismatch.label("sustained_mismatch"),
        )
        .join(School, School.id == Line.school_id)
        .where(Line.status == filters.line_status)
    )
    if filters.school_id is not None:
        query = query.where(School.id == filters.school_id)
    else:
        query = query.where(School.is_active)
    if filters.region_id is not None:
        query = query.where(School.region_id == filters.region_id)
    if filters.provider_id is not None:
        query = query.where(Line.provider_id == filters.provider_id)
    if filters.connection_type_id is not None:
        query = query.where(Line.connection_type_id == filters.connection_type_id)
    selected = query.subquery()

    key: ColumnElement[Any] | None = {
        "school": selected.c.school_id,
        "district": selected.c.region_id,
        "provider": selected.c.provider_id,
    }.get(level)

    def in_period(source: Any, width: timedelta) -> list[ColumnElement[bool]]:
        # A bucket that overlaps the period counts whole: the aggregates do not go finer.
        return [source.bucket > start - width, source.bucket < end]

    def measured(source: Any) -> Select[Any]:
        return select(
            func.sum(source.measurements_count).label("measurements_count"),
            func.sum(source.problem_count).label("problem_count"),
            *(
                weighted(getattr(source, f"avg_{metric}"), source.measurements_count).label(
                    f"avg_{metric}"
                )
                for metric in METRICS
            ),
        ).join(selected, selected.c.line_id == source.line_id)

    width = BUCKET_WIDTH[granularity]
    totals = measured(rollup).add_columns(
        *(func.min(getattr(rollup, f"min_{metric}")).label(f"min_{metric}") for metric in METRICS),
        *(func.max(getattr(rollup, f"max_{metric}")).label(f"max_{metric}") for metric in METRICS),
        func.sum(case((selected.c.has_contract, rollup.below_contract_count), else_=0)).label(
            "below_contract_count"
        ),
        func.sum(case((selected.c.has_contract, rollup.measurements_count), else_=0)).label(
            "contract_count"
        ),
    )
    totals = totals.where(*in_period(rollup, width))
    if key is not None:
        totals = totals.add_columns(key.label("key")).group_by(key)
    measured_rows = {getattr(row, "key", None): row for row in await session.execute(totals)}

    entities: list[tuple[int | None, str | None]]
    if level == "school":
        names = select(School.id, School.full_name).where(
            School.id.in_(select(selected.c.school_id))
        )
        entities = [
            (i, name) for i, name in await session.execute(names.order_by(School.full_name))
        ]
    elif level == "district":
        names = select(Region.id, Region.name).where(Region.id.in_(select(selected.c.region_id)))
        entities = [(i, name) for i, name in await session.execute(names.order_by(Region.name))]
    elif level == "provider":
        names = select(Provider.id, Provider.name).where(
            Provider.id.in_(select(selected.c.provider_id))
        )
        entities = [(i, name) for i, name in await session.execute(names.order_by(Provider.name))]
    else:
        entities = [(None, None)]

    # Availability of the schools behind every row: downtime over observed time of them all.
    schools_of: dict[int | None, set[int]] = defaultdict(set)
    pairs = select(selected.c.school_id)
    if key is not None:
        pairs = pairs.add_columns(key.label("key"))
    for pair in await session.execute(pairs.distinct()):
        schools_of[getattr(pair, "key", None)].add(pair.school_id)
    availability = await schools_availability(
        session, {i for ids in schools_of.values() for i in ids}, start=start, end=end
    )

    def availability_pct(entity_id: int | None) -> float | None:
        observed = [
            availability[i] for i in schools_of[entity_id] if availability[i].uptime_pct is not None
        ]
        observed_s = sum(item.observed_s for item in observed)
        if not observed_s:
            return None
        return 100 * (1 - sum(item.downtime_s for item in observed) / observed_s)

    # Sustained mismatch is the current state of a line, not a number of the period (T-29):
    # lines of the row with the flag set, empty while none of them has been recomputed.
    mismatch = select(
        func.count().filter(selected.c.sustained_mismatch).label("lines_count"),
        func.count(selected.c.sustained_mismatch).label("rated_count"),
    )
    if key is not None:
        mismatch = mismatch.add_columns(key.label("key")).group_by(key)
    mismatch_rows = {getattr(row, "key", None): row for row in await session.execute(mismatch)}

    def sustained_mismatch_lines_count(entity_id: int | None) -> int | None:
        row = mismatch_rows.get(entity_id)
        return int(row.lines_count) if row and row.rated_count else None

    rows = []
    for entity_id, name in entities:
        row = measured_rows.get(entity_id)
        count = int(row.measurements_count or 0) if row else 0
        problems = int(row.problem_count or 0) if row else 0
        contract_count = int(row.contract_count or 0) if row else 0
        rows.append(
            AnalyticsRow(
                id=entity_id,
                name=name,
                measurements_count=count,
                problem_count=problems,
                problem_pct=percent(problems, count),
                download_mbps=stats(row, "download_mbps") if row else None,
                upload_mbps=stats(row, "upload_mbps") if row else None,
                ping_ms=stats(row, "ping_ms") if row else None,
                availability_pct=availability_pct(entity_id),
                below_contract_pct=percent(int(row.below_contract_count or 0), contract_count)
                if row
                else None,
                sustained_mismatch_lines_count=sustained_mismatch_lines_count(entity_id),
            )
        )

    series = [
        AnalyticsSeriesPoint(
            bucket_start=row.bucket,
            measurements_count=row.measurements_count,
            problem_count=row.problem_count,
            problem_pct=100 * row.problem_count / row.measurements_count,
            avg_download_mbps=row.avg_download_mbps,
            avg_upload_mbps=row.avg_upload_mbps,
            avg_ping_ms=row.avg_ping_ms,
        )
        for row in await session.execute(
            measured(rollup)
            .add_columns(rollup.bucket.label("bucket"))
            .where(*in_period(rollup, width))
            .group_by(rollup.bucket)
            .order_by(rollup.bucket)
        )
        if row.measurements_count
    ]

    # Grouped over a sub-query: the zone is a bound parameter, so the same expression written
    # twice would be two different ones for PostgreSQL.
    local = func.timezone(settings.timezone, MHourly.bucket)
    cells = (
        select(
            extract("isodow", local).label("weekday"),
            extract("hour", local).label("hour"),
            MHourly.measurements_count,
            MHourly.problem_count,
        )
        .join(selected, selected.c.line_id == MHourly.line_id)
        .where(*in_period(MHourly, BUCKET_WIDTH["hour"]))
        .subquery()
    )
    heatmap = [
        AnalyticsHeatmapCell(
            weekday=WEEKDAYS[int(row.weekday) - 1],
            hour=int(row.hour),
            measurements_count=row.measurements_count,
            problem_count=row.problem_count,
            problem_pct=100 * row.problem_count / row.measurements_count,
        )
        for row in await session.execute(
            select(
                cells.c.weekday,
                cells.c.hour,
                func.sum(cells.c.measurements_count).label("measurements_count"),
                func.sum(cells.c.problem_count).label("problem_count"),
            )
            .group_by(cells.c.weekday, cells.c.hour)
            .order_by(cells.c.weekday, cells.c.hour)
        )
        if row.measurements_count
    ]

    return AnalyticsReport(
        period_from=start,
        period_to=end,
        granularity=granularity,
        thresholds=await chart_thresholds(session, selected, filters),
        availability_min_pct=settings.availability_min_pct,
        rows=rows,
        series=series,
        heatmap=heatmap,
    )


async def chart_thresholds(
    session: AsyncSession, selected: Any, filters: AnalyticsFilters
) -> ThresholdValues:
    """Thresholds the charts are marked with: the line's chain when the selection is one line,
    the district's with ``region_id``, the global profile otherwise (ADR-004)."""
    lines = (await session.execute(select(selected.c.line_id, selected.c.region_id))).all()
    if len(lines) == 1:
        profile = await threshold_profile(
            session, line_id=lines[0].line_id, region_id=lines[0].region_id
        )
    else:
        profile = await threshold_profile(session, line_id=None, region_id=filters.region_id)
    if profile is None:
        raise ApiError(503, NOT_CONFIGURED, NOT_CONFIGURED_DETAIL)
    return ThresholdValues.model_validate(profile, from_attributes=True)
