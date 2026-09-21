"""Overview and map of the panel (T-22): the KPIs of ТЗ п. 4 and the schools on the map (п. 13).

Both answer the same filters, so one filter panel drives both screens. A school is selected by
its district, by a line of the provider or connection type, and by its status at ``period_to``
(ADR-004); the status is computed first, so the status filter sees exactly what the map shows.
Every query runs in the session of the request, so RLS limits it to the user's scope (ADR-008).
Measurement values cover main lines only and never Wi-Fi (ADR-012).
"""

import json
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConnectionType,
    Device,
    Heartbeat,
    Line,
    Measurement,
    MonitoringPoint,
    Provider,
    Region,
    School,
)
from app.schemas.dashboard import DashboardPeriodKpis, DashboardSummary, SchoolStatusCounts
from app.schemas.map import (
    MapFilterOption,
    MapFilterOptions,
    RegionMapFeatureCollection,
    SchoolMapFeatureCollection,
)
from app.schemas.statuses import SchoolStatus
from app.services.status import WIFI, school_statuses

# Statuses of a problem device: its last measurement is past the thresholds or offline.
PROBLEM_STATUSES = ("unstable", "critical", "offline")


@dataclass(frozen=True)
class OverviewFilters:
    """Filters shared by ``GET /api/dashboard/summary`` and ``GET /api/map/schools``."""

    region_id: int | None = None
    provider_id: int | None = None
    connection_type_id: int | None = None
    statuses: Sequence[SchoolStatus] | None = None


def school_candidates(filters: OverviewFilters, *, only_active: bool = True) -> Select[Any]:
    """Ids of the schools the district, provider and connection-type filters select.

    The status filter is not one of them: it is applied to the statuses afterwards by ``narrow``,
    so the counters of the status strip see the whole selection (docs/design/README.md §4.1).
    """
    query = select(School.id)
    if only_active:
        query = query.where(School.is_active)
    if filters.region_id is not None:
        query = query.where(School.region_id == filters.region_id)
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
    return query


async def school_selection(
    session: AsyncSession, filters: OverviewFilters, *, now: datetime
) -> dict[int, SchoolStatus]:
    """Every candidate school with its status at ``now``, before the status filter (T-60)."""
    school_ids = list(await session.scalars(school_candidates(filters)))
    return await school_statuses(session, school_ids, now=now)


def narrow(
    statuses: dict[int, SchoolStatus], wanted: Sequence[SchoolStatus] | None
) -> dict[int, SchoolStatus]:
    """Schools of ``statuses`` whose status is one of ``wanted``; all of them when it is empty."""
    if not wanted:
        return statuses
    return {i: status for i, status in statuses.items() if status in wanted}


async def selected_schools(
    session: AsyncSession, filters: OverviewFilters, *, now: datetime
) -> dict[int, SchoolStatus]:
    """Active schools matching the filters, with their status at ``now``, by id."""
    return narrow(await school_selection(session, filters, now=now), filters.statuses)


def status_counts(statuses: dict[int, SchoolStatus]) -> SchoolStatusCounts:
    """Schools per status; every status is present, so the five sum to the selection (T-60)."""
    counted = Counter(statuses.values())
    return SchoolStatusCounts(
        normal=counted["normal"],
        unstable=counted["unstable"],
        critical=counted["critical"],
        offline=counted["offline"],
        no_data=counted["no_data"],
    )


async def schools_in_registry(session: AsyncSession, filters: OverviewFilters) -> int:
    """Schools of the same filters together with the switched-off ones: «350 из 366 в реестре»."""
    query = select(func.count()).select_from(
        school_candidates(filters, only_active=False).subquery()
    )
    return await session.scalar(query) or 0


def main_line_measurements(
    school_ids: Collection[int], period_from: datetime | None, period_to: datetime
) -> list[ColumnElement[bool]]:
    """Conditions of the measurements the KPIs and the map count: main lines, no Wi-Fi.

    For a query of ``measurements`` joined with ``lines``.
    """
    conditions = [
        Line.school_id.in_(school_ids),
        Line.status == "main",
        Measurement.iface_type.is_distinct_from(WIFI),
        Measurement.measured_at < period_to,
    ]
    if period_from is not None:
        conditions.append(Measurement.measured_at >= period_from)
    return conditions


def registered_devices(school_ids: Collection[int]) -> Select[Any]:
    """Count of the computers of the schools that are not blocked (ТЗ п. 4, ADR-005)."""
    return (
        select(func.count())
        .select_from(Device)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(MonitoringPoint.school_id.in_(school_ids), Device.status == "active")
    )


def no_measurements() -> DashboardPeriodKpis:
    """KPIs of a period in which nothing was measured and nobody was heard."""
    return DashboardPeriodKpis(
        active_devices_count=0,
        measurements_count=0,
        avg_download_mbps=None,
        avg_upload_mbps=None,
        avg_ping_ms=None,
        problem_devices_count=0,
    )


def has_data(kpis: DashboardPeriodKpis) -> bool:
    """Whether a period is worth comparing with: something was measured or somebody was heard."""
    return kpis.measurements_count > 0 or kpis.active_devices_count > 0


async def period_kpis(
    session: AsyncSession,
    school_ids: Collection[int],
    *,
    period_from: datetime,
    period_to: datetime,
) -> DashboardPeriodKpis:
    """KPIs of ТЗ п. 4 that depend on the period, over the given schools.

    The schools are passed in and never re-selected, so the previous period of ``previous``
    answers over exactly the same schools as the current one: a school added in between would
    otherwise read as a school that changed (T-60).
    """
    devices = registered_devices(school_ids)
    heard = (
        select(Heartbeat.device_id)
        .where(
            Heartbeat.device_id == Device.id,
            Heartbeat.ts >= period_from,
            Heartbeat.ts < period_to,
        )
        .exists()
    )
    measured = (
        select(Measurement.id)
        .where(
            Measurement.device_id == Device.id,
            Measurement.measured_at >= period_from,
            Measurement.measured_at < period_to,
        )
        .exists()
    )

    counted = main_line_measurements(school_ids, period_from, period_to)
    totals = (
        await session.execute(
            select(
                func.count(),
                func.avg(Measurement.download_mbps),
                func.avg(Measurement.upload_mbps),
                func.avg(Measurement.ping_ms),
            )
            .join(Line, Line.id == Measurement.line_id)
            .where(*counted)
        )
    ).one()
    last = (
        select(Measurement.device_id, Measurement.quality_status)
        .join(Line, Line.id == Measurement.line_id)
        .where(*counted)
        .distinct(Measurement.device_id)
        .order_by(Measurement.device_id, Measurement.measured_at.desc())
        .subquery()
    )
    problem_devices = select(func.count()).where(last.c.quality_status.in_(PROBLEM_STATUSES))

    return DashboardPeriodKpis(
        active_devices_count=await session.scalar(devices.where(or_(heard, measured))) or 0,
        measurements_count=totals[0],
        avg_download_mbps=totals[1],
        avg_upload_mbps=totals[2],
        avg_ping_ms=totals[3],
        problem_devices_count=await session.scalar(problem_devices) or 0,
    )


async def dashboard_summary(
    session: AsyncSession,
    filters: OverviewFilters,
    *,
    period_from: datetime,
    period_to: datetime,
) -> DashboardSummary:
    """The KPIs of ТЗ п. 4, the status strip and the previous period over the selected schools.

    The strip is counted before the status filter and the registry count includes the
    switched-off schools, so «312 из 350» and «350 из 366 в реестре» of the main screen come
    from one request (docs/design/README.md §4.1, T-60).
    """
    all_statuses = await school_selection(session, filters, now=period_to)
    counts = status_counts(all_statuses)
    total_in_registry = await schools_in_registry(session, filters)
    school_ids = list(narrow(all_statuses, filters.statuses))
    common = {
        "period_from": period_from,
        "period_to": period_to,
        "schools_count": len(school_ids),
        "schools_total_count": total_in_registry,
        "status_counts": counts,
    }
    if not school_ids:
        return DashboardSummary.model_validate(
            no_measurements().model_dump() | common | {"devices_count": 0, "previous": None},
        )

    current = await period_kpis(session, school_ids, period_from=period_from, period_to=period_to)
    length = period_to - period_from
    earlier = await period_kpis(
        session, school_ids, period_from=period_from - length, period_to=period_from
    )
    return DashboardSummary.model_validate(
        current.model_dump()
        | common
        | {
            "devices_count": await session.scalar(registered_devices(school_ids)) or 0,
            "previous": earlier if has_data(earlier) else None,
        },
    )


async def school_map(
    session: AsyncSession,
    filters: OverviewFilters,
    *,
    period_from: datetime | None,
    period_to: datetime,
) -> SchoolMapFeatureCollection:
    """Selected schools as GeoJSON: the main line and its last measurement in the period."""
    statuses = await selected_schools(session, filters, now=period_to)
    if not statuses:
        return SchoolMapFeatureCollection(type="FeatureCollection", features=[])

    # The first main line of a school is the one the popover describes.
    main_line = (
        select(Line)
        .where(Line.status == "main")
        .distinct(Line.school_id)
        .order_by(Line.school_id, Line.id)
        .subquery()
    )
    last = (
        select(
            Measurement.download_mbps,
            Measurement.upload_mbps,
            Measurement.ping_ms,
            Measurement.measured_at,
            Measurement.thresholds_snapshot,
        )
        .join(Line, Line.id == Measurement.line_id)
        .where(
            *main_line_measurements(list(statuses), period_from, period_to),
            Line.school_id == School.id,
        )
        .order_by(Measurement.measured_at.desc())
        .limit(1)
        .lateral("last")
    )
    rows = await session.execute(
        select(
            School.id,
            School.school_code,
            School.full_name,
            func.ST_X(School.geom).label("lon"),
            func.ST_Y(School.geom).label("lat"),
            Region.name.label("region_name"),
            Provider.name.label("provider_name"),
            ConnectionType.name.label("connection_type_name"),
            main_line.c.contract_down_mbps,
            main_line.c.contract_up_mbps,
            last.c.download_mbps,
            last.c.upload_mbps,
            last.c.ping_ms,
            last.c.measured_at,
            last.c.thresholds_snapshot,
        )
        .join(Region, Region.id == School.region_id)
        .outerjoin(main_line, main_line.c.school_id == School.id)
        .outerjoin(Provider, Provider.id == main_line.c.provider_id)
        .outerjoin(ConnectionType, ConnectionType.id == main_line.c.connection_type_id)
        .outerjoin(last, true())
        .where(School.id.in_(statuses))
        .order_by(School.full_name)
    )
    features = []
    for row in rows:
        snapshot = row.thresholds_snapshot or {}
        features.append(
            {
                "type": "Feature",
                "id": row.id,
                "geometry": None
                if row.lon is None
                else {"type": "Point", "coordinates": (row.lon, row.lat)},
                "properties": {
                    "school_code": row.school_code,
                    "full_name": row.full_name,
                    "region_name": row.region_name,
                    "provider_name": row.provider_name,
                    "connection_type_name": row.connection_type_name,
                    "contract_down_mbps": row.contract_down_mbps,
                    "contract_up_mbps": row.contract_up_mbps,
                    "status": statuses[row.id],
                    "download_mbps": row.download_mbps,
                    "upload_mbps": row.upload_mbps,
                    "ping_ms": row.ping_ms,
                    "last_measured_at": row.measured_at,
                    "download_min_mbps": snapshot.get("download_min_mbps"),
                    "upload_min_mbps": snapshot.get("upload_min_mbps"),
                    "ping_max_ms": snapshot.get("ping_max_ms"),
                },
            }
        )
    return SchoolMapFeatureCollection.model_validate(
        {"type": "FeatureCollection", "features": features}
    )


async def region_boundaries(session: AsyncSession) -> RegionMapFeatureCollection:
    """Boundaries of every district and city of VKO, by name."""
    rows = await session.execute(
        select(Region.id, Region.code, Region.name, func.ST_AsGeoJSON(Region.geom)).order_by(
            Region.name
        )
    )
    return RegionMapFeatureCollection.model_validate(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": region_id,
                    "geometry": json.loads(geometry) if geometry else None,
                    "properties": {"code": code, "name": name},
                }
                for region_id, code, name, geometry in rows
            ],
        }
    )


async def filter_options(session: AsyncSession) -> MapFilterOptions:
    """Districts, providers and connection types the user can filter by (ADR-008)."""

    async def options(query: Select[Any]) -> list[MapFilterOption]:
        return [MapFilterOption(id=i, name=name) for i, name in await session.execute(query)]

    visible_lines = select(Line).where(Line.status != "disabled").subquery()
    return MapFilterOptions(
        regions=await options(
            select(Region.id, Region.name)
            .where(Region.id.in_(select(School.region_id).where(School.is_active)))
            .order_by(Region.name)
        ),
        providers=await options(
            select(Provider.id, Provider.name)
            .where(Provider.id.in_(select(visible_lines.c.provider_id)))
            .order_by(Provider.name)
        ),
        connection_types=await options(
            select(ConnectionType.id, ConnectionType.name)
            .where(ConnectionType.id.in_(select(visible_lines.c.connection_type_id)))
            .order_by(ConnectionType.name)
        ),
    )
