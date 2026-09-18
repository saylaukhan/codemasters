"""School card of the panel (T-25, ТЗ п. 4, п. 13–15): state, computers, lines, contacts.

Every query runs in the session of the request, so RLS limits it to the user's scope: a school
outside it is «не найдена», not «запрещена» — its existence is not disclosed (ADR-008). The
current values are the last measurement of the main line without Wi-Fi (ADR-012), the same one
the list and the map show.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import Select, case, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import (
    ConnectionType,
    Device,
    Line,
    Measurement,
    MonitoringPoint,
    Provider,
    Region,
    School,
    SchoolContact,
)
from app.schemas.devices import DeviceListItem, DeviceListItemPage, LatestMeasurement
from app.schemas.schools import (
    LineDetail,
    LineDetailPage,
    SchoolContactDetail,
    SchoolContactDetailPage,
    SchoolDetail,
    WorkingHours,
)
from app.schemas.statuses import SchoolStatus
from app.services.settings import system_settings
from app.services.status import WIFI, school_statuses, worst_of_the_majority
from app.services.working_hours import is_working_time

# Order of the lines in the card: the main one first, the switched-off ones last.
LINE_ORDER = case({"main": 0, "reserve": 1, "disabled": 2}, value=Line.status)


def school_not_found() -> ApiError:
    return ApiError(404, "not_found", "Школа не найдена")


async def ensure_school(session: AsyncSession, school_id: int) -> None:
    """404 unless the school exists and is in the user's scope."""
    if await session.scalar(select(School.id).where(School.id == school_id)) is None:
        raise school_not_found()


def latest_measurement(measurement: Measurement | None) -> LatestMeasurement | None:
    if measurement is None:
        return None
    return LatestMeasurement.model_validate(
        {
            "measured_at": measurement.measured_at,
            "connection_status": measurement.connection_status,
            "download_mbps": measurement.download_mbps,
            "upload_mbps": measurement.upload_mbps,
            "ping_ms": measurement.ping_ms,
            "jitter_ms": measurement.jitter_ms,
            "packet_loss_pct": measurement.packet_loss_pct,
            "iface_type": measurement.iface_type,
            "thresholds_snapshot": measurement.thresholds_snapshot,
            "quality_status": measurement.quality_status,
        }
    )


async def school_detail(session: AsyncSession, school_id: int, *, now: datetime) -> SchoolDetail:
    row = (
        await session.execute(
            select(
                School.id,
                School.school_code,
                School.full_name,
                School.region_id,
                Region.name.label("region_name"),
                School.address,
                func.ST_X(School.geom).label("lon"),
                func.ST_Y(School.geom).label("lat"),
                School.is_active,
            )
            .join(Region, Region.id == School.region_id)
            .where(School.id == school_id)
        )
    ).one_or_none()
    if row is None:
        raise school_not_found()
    settings = await system_settings(session)

    rated = (
        select(Measurement)
        .join(Line, Line.id == Measurement.line_id)
        .where(
            Line.school_id == school_id,
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.measured_at <= now,
        )
        .order_by(Measurement.measured_at.desc())
        .limit(1)
    )
    on_main = await session.scalar(rated.where(Line.status == "main"))
    # The newest measurement through any line: a reserve one means the main line is down.
    newest_line = await session.scalar(
        select(Line.status).where(
            Line.id == rated.with_only_columns(Measurement.line_id).scalar_subquery()
        )
    )
    return SchoolDetail.model_validate(
        {
            "id": row.id,
            "school_code": row.school_code,
            "full_name": row.full_name,
            "region_id": row.region_id,
            "region_name": row.region_name,
            "address": row.address,
            "location": None if row.lon is None else {"lat": row.lat, "lon": row.lon},
            "is_active": row.is_active,
            # Schools have no hours of their own until T-37: the admin defaults apply.
            "working_hours": settings.default_working_hours,
            "status": (await school_statuses(session, [school_id], now=now))[school_id],
            "on_reserve_line": newest_line == "reserve",
            "latest_measurement": latest_measurement(on_main),
        }
    )


async def device_items(
    session: AsyncSession, rows: Sequence[Any], *, now: datetime
) -> list[DeviceListItem]:
    """Rows of ``Device, MonitoringPoint, line_status`` with the last measurement and the
    current status of each computer; shared by the school card and the device card (T-26)."""
    settings = await system_settings(session)
    hours = WorkingHours.model_validate(settings.default_working_hours)
    silent: SchoolStatus = (
        "offline" if is_working_time(hours, settings.timezone, now) else "no_data"
    )
    latest: dict[int, Measurement] = {
        measurement.device_id: measurement
        for measurement in await session.scalars(
            select(Measurement)
            .where(
                Measurement.device_id.in_([row.Device.id for row in rows]),
                Measurement.measured_at <= now,
            )
            .distinct(Measurement.device_id)
            .order_by(Measurement.device_id, Measurement.measured_at.desc())
        )
    }

    def current_status(device: Device) -> SchoolStatus:
        if device.status == "blocked":
            return "no_data"
        seen = device.last_seen_at
        if seen is None or now - seen > timedelta(seconds=settings.offline_after_s):
            return silent
        measurement = latest.get(device.id)
        if measurement is None or measurement.quality_status is None:
            return "no_data"
        return cast(SchoolStatus, measurement.quality_status)

    return [
        DeviceListItem.model_validate(
            {
                "id": row.Device.id,
                "device_uid": row.Device.device_uid,
                "hostname": row.Device.hostname,
                "monitoring_point_id": row.MonitoringPoint.id,
                "monitoring_point_name": row.MonitoringPoint.name,
                "room": row.MonitoringPoint.room,
                "line_id": row.MonitoringPoint.line_id,
                "line_status": row.line_status,
                "agent_version": row.Device.agent_version,
                "last_seen_at": row.Device.last_seen_at,
                "status": row.Device.status,
                "current_status": current_status(row.Device),
                "latest_measurement": latest_measurement(latest.get(row.Device.id)),
            }
        )
        for row in rows
    ]


def device_rows() -> Select[Any]:
    """Devices with their monitoring point and the status of its line."""
    return (
        select(Device, MonitoringPoint, Line.status.label("line_status"))
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .join(Line, Line.id == MonitoringPoint.line_id)
    )


async def school_devices(
    session: AsyncSession, school_id: int, params: PageParams, *, now: datetime
) -> DeviceListItemPage:
    """Computers of the school with their last measurement and status (ТЗ п. 4)."""
    await ensure_school(session, school_id)
    query = device_rows().where(MonitoringPoint.school_id == school_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await session.execute(
            query.order_by(MonitoringPoint.is_primary.desc(), MonitoringPoint.name, Device.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
    ).all()
    return DeviceListItemPage(
        items=await device_items(session, rows, now=now),
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def school_lines(
    session: AsyncSession, school_id: int, params: PageParams, *, now: datetime
) -> LineDetailPage:
    """Lines of the school with their provider, contract and current quality (ТЗ п. 10, п. 14)."""
    await ensure_school(session, school_id)
    settings = await system_settings(session)
    query = (
        select(Line, Provider.name.label("provider_name"), ConnectionType.name.label("type_name"))
        .join(Provider, Provider.id == Line.provider_id)
        .outerjoin(ConnectionType, ConnectionType.id == Line.connection_type_id)
        .where(Line.school_id == school_id)
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await session.execute(
            query.order_by(LINE_ORDER, Line.id).offset(params.offset).limit(params.page_size)
        )
    ).all()

    # Quality of a line: the rule of the school status over its last Ethernet measurements.
    latest = (
        select(Measurement.measured_at, Measurement.quality_status)
        .where(
            Measurement.line_id == Line.id,
            Measurement.measured_at <= now,
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.quality_status.is_not(None),
        )
        .order_by(Measurement.measured_at.desc())
        .limit(settings.school_status_measurements_count)
        .lateral("latest")
    )
    series: dict[int, list[str]] = defaultdict(list)
    for line_id, quality_status in await session.execute(
        select(Line.id, latest.c.quality_status)
        .join(latest, true())
        .where(Line.id.in_([row.Line.id for row in rows]))
    ):
        series[line_id].append(quality_status)

    def detail(row: Any) -> LineDetail:
        line: Line = row.Line
        return LineDetail.model_validate(
            {
                "id": line.id,
                "school_id": line.school_id,
                "provider_id": line.provider_id,
                "provider_name": row.provider_name,
                "connection_type_id": line.connection_type_id,
                "connection_type_name": row.type_name,
                "line_identifier": line.line_identifier,
                "status": line.status,
                "contract_down_mbps": line.contract_down_mbps,
                "contract_up_mbps": line.contract_up_mbps,
                "contract_number": line.contract_number,
                "contract_date": line.contract_date,
                "started_at": line.started_at,
                "ip_ranges": line.ip_ranges,
                "quality_status": worst_of_the_majority(series[line.id])
                if series[line.id]
                else None,
                # Written by the periodic recompute of T-29; empty until it has something.
                "contract_compliance": {
                    "sustained_mismatch": line.compliance_sustained_mismatch,
                    "below_contract_pct": line.compliance_below_pct,
                    "window_days": line.compliance_window_days,
                }
                if line.compliance_checked_at is not None
                else None,
            }
        )

    return LineDetailPage(
        items=[detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def school_contacts(
    session: AsyncSession, school_id: int, params: PageParams, *, show_phone: bool
) -> SchoolContactDetailPage:
    """Responsible people of the school (ТЗ п. 15); the phone only for a role with the right."""
    await ensure_school(session, school_id)
    query = select(SchoolContact).where(SchoolContact.school_id == school_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    contacts = await session.scalars(
        query.order_by(SchoolContact.id).offset(params.offset).limit(params.page_size)
    )
    return SchoolContactDetailPage(
        items=[
            SchoolContactDetail(
                id=contact.id,
                school_id=contact.school_id,
                full_name=contact.full_name,
                position=contact.position,
                phone=contact.phone if show_phone else None,
                email=contact.email,
                provider_support_contact=contact.provider_support_contact,
                updated_at=contact.updated_at,
            )
            for contact in contacts
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
