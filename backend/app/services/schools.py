"""School list of the panel (T-24, ТЗ п. 4): averages, devices, last measurement and status.

The status is computed in Python (``school_statuses``), so filtering and sorting by it happen
here too: the list is assembled for every school that matches the filters, sorted, then cut into
a page. The region has a few hundred schools, which is well within one request. Averages come
from ``m_daily`` (T-19): main lines only, never Wi-Fi (ADR-012). Every query runs in the session
of the request, so RLS limits it to the user's scope (ADR-008).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, MDaily, Measurement, MonitoringPoint, Region, School
from app.schemas.schools import SchoolListItem, SchoolListItemPage, SchoolSort
from app.schemas.statuses import SchoolStatus
from app.schemas.thresholds import ThresholdValues
from app.services.status import WIFI, school_statuses
from app.services.thresholds import threshold_profile

# Order of ``sort=status``: the best first, «Нет данных» after every status of quality.
STATUS_ORDER: dict[SchoolStatus, int] = {
    "normal": 0,
    "unstable": 1,
    "critical": 2,
    "offline": 3,
    "no_data": 4,
}


@dataclass(frozen=True)
class SchoolListFilters:
    region_id: int | None = None
    provider_id: int | None = None
    connection_type_id: int | None = None
    statuses: Sequence[SchoolStatus] | None = None
    is_active: bool | None = None
    q: str | None = None


async def school_list(
    session: AsyncSession,
    filters: SchoolListFilters,
    *,
    period_from: datetime,
    period_to: datetime,
    sort: SchoolSort | None,
    page: int,
    page_size: int,
) -> SchoolListItemPage:
    query = select(
        School.id,
        School.school_code,
        School.full_name,
        School.region_id,
        Region.name,
        School.is_active,
    ).join(Region, Region.id == School.region_id)
    if filters.region_id is not None:
        query = query.where(School.region_id == filters.region_id)
    if filters.is_active is not None:
        query = query.where(School.is_active == filters.is_active)
    if filters.q:
        pattern = f"%{filters.q}%"
        query = query.where(or_(School.full_name.ilike(pattern), School.school_code.ilike(pattern)))
    line_filters = []
    if filters.provider_id is not None:
        line_filters.append(Line.provider_id == filters.provider_id)
    if filters.connection_type_id is not None:
        line_filters.append(Line.connection_type_id == filters.connection_type_id)
    if line_filters:
        query = query.where(
            select(Line.id)
            .where(Line.school_id == School.id, Line.status != "disabled", *line_filters)
            .exists()
        )
    schools = {row.id: row for row in await session.execute(query)}
    statuses = await school_statuses(session, list(schools), now=period_to)
    if filters.statuses:
        schools = {i: row for i, row in schools.items() if statuses[i] in filters.statuses}
    ids = list(schools)

    devices: dict[int, int] = {}
    averages: dict[int, Any] = {}
    last_measured: dict[int, datetime] = {}
    if ids:
        devices = {
            school_id: count
            for school_id, count in await session.execute(
                select(MonitoringPoint.school_id, func.count())
                .join(Device, Device.monitoring_point_id == MonitoringPoint.id)
                .where(MonitoringPoint.school_id.in_(ids), Device.status == "active")
                .group_by(MonitoringPoint.school_id)
            )
        }

        # A day bucket overlapping the window counts whole: m_daily does not go finer.
        def weighted(column: Any) -> Any:
            counted = func.sum(case((column.is_not(None), MDaily.measurements_count), else_=0))
            return func.sum(column * MDaily.measurements_count) / func.nullif(counted, 0)

        averages = {
            row.school_id: row
            for row in await session.execute(
                select(
                    Line.school_id,
                    weighted(MDaily.avg_download_mbps).label("download"),
                    weighted(MDaily.avg_upload_mbps).label("upload"),
                    weighted(MDaily.avg_ping_ms).label("ping"),
                )
                .join(Line, Line.id == MDaily.line_id)
                .where(
                    Line.school_id.in_(ids),
                    Line.status == "main",
                    MDaily.bucket > period_from - timedelta(days=1),
                    MDaily.bucket < period_to,
                )
                .group_by(Line.school_id)
            )
        }
        last_measured = {
            school_id: moment
            for school_id, moment in await session.execute(
                select(Line.school_id, func.max(Measurement.measured_at))
                .join(Line, Line.id == Measurement.line_id)
                .where(
                    Line.school_id.in_(ids),
                    Line.status == "main",
                    Measurement.iface_type.is_distinct_from(WIFI),
                    Measurement.measured_at <= period_to,
                )
                .group_by(Line.school_id)
            )
        }

    def average(school_id: int, name: str) -> float | None:
        row = averages.get(school_id)
        value = getattr(row, name) if row else None
        return None if value is None else float(value)

    items = [
        {
            "id": i,
            "school_code": row.school_code,
            "full_name": row.full_name,
            "region_id": row.region_id,
            "region_name": row.name,
            "is_active": row.is_active,
            "devices_count": devices.get(i, 0),
            "avg_download_mbps": average(i, "download"),
            "avg_upload_mbps": average(i, "upload"),
            "avg_ping_ms": average(i, "ping"),
            "last_measured_at": last_measured.get(i),
            "status": statuses[i],
            "thresholds": None,
        }
        for i, row in schools.items()
    ]

    field = (sort or "full_name").lstrip("-")
    descending = bool(sort and sort.startswith("-"))

    def key(item: dict[str, Any]) -> Any:
        value = STATUS_ORDER[item["status"]] if field == "status" else item[field]
        return value.casefold() if isinstance(value, str) else value

    # Empty values go last in both directions; the name breaks ties.
    items.sort(key=lambda item: item["full_name"].casefold())
    present = [item for item in items if item[field] is not None]
    present.sort(key=key, reverse=descending)
    items = present + [item for item in items if item[field] is None]

    chunk = items[(page - 1) * page_size : page * page_size]
    for item in chunk:
        item["thresholds"] = await main_line_thresholds(session, item["id"], item["region_id"])
    return SchoolListItemPage(
        items=[SchoolListItem.model_validate(item) for item in chunk],
        total=len(items),
        page=page,
        page_size=page_size,
    )


async def main_line_thresholds(
    session: AsyncSession, school_id: int, region_id: int
) -> ThresholdValues | None:
    """Thresholds in force on the first main line of the school; none without a main line."""
    line_id = await session.scalar(
        select(Line.id)
        .where(Line.school_id == school_id, Line.status == "main")
        .order_by(Line.id)
        .limit(1)
    )
    if line_id is None:
        return None
    profile = await threshold_profile(session, line_id=line_id, region_id=region_id)
    return (
        None if profile is None else ThresholdValues.model_validate(profile, from_attributes=True)
    )
