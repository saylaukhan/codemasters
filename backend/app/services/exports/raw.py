"""Raw measurements of an export (T-30, ТЗ п. 9): one record per measurement of the selection.

The query runs in the session of the request, so RLS keeps it inside the user's scope
(ADR-008); a school or a computer of the request the user cannot see is a 422, not an empty
file. The school of a measurement is the school of its line; the computer and its room are
joined outward, so a measurement stays in the file even if its computer moved elsewhere.
Date and time are local ones of ``settings.timezone`` (ADR-014).
"""

from collections.abc import Sequence
from datetime import tzinfo
from typing import Any

from fastapi.exceptions import RequestValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, Measurement, MonitoringPoint, School
from app.schemas.exports import ExportCreate


def invalid_ids(field: str, noun: str, ids: Sequence[int]) -> RequestValidationError:
    message = f"{noun} не найдены или вне области видимости: {', '.join(map(str, ids))}"
    return RequestValidationError(
        [{"type": "value_error", "loc": ("body", field), "msg": message, "ctx": {"error": message}}]
    )


async def check_selection(session: AsyncSession, body: ExportCreate) -> None:
    """422 when a school or a computer of the request is unknown, outside the scope or, for a
    computer, not of the chosen schools."""
    if body.school_ids:
        visible = await session.scalars(select(School.id).where(School.id.in_(body.school_ids)))
        missing = sorted(set(body.school_ids) - set(visible))
        if missing:
            raise invalid_ids("school_ids", "Школы", missing)
    if body.device_ids:
        query = (
            select(Device.id)
            .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
            .where(Device.id.in_(body.device_ids))
        )
        if body.school_ids:
            query = query.where(MonitoringPoint.school_id.in_(body.school_ids))
        missing = sorted(set(body.device_ids) - set(await session.scalars(query)))
        if missing:
            raise invalid_ids("device_ids", "Компьютеры", missing)


def raw_query(body: ExportCreate) -> Select[Any]:
    """Measurements of the selection with their school, computer and room, in file order."""
    query = (
        select(
            School.full_name,
            School.school_code,
            Line.status.label("line_status"),
            Measurement.device_id,
            func.coalesce(Device.hostname, Device.device_uid).label("hostname"),
            MonitoringPoint.room,
            Measurement.measured_at,
            Measurement.download_mbps,
            Measurement.upload_mbps,
            Measurement.ping_ms,
            Measurement.jitter_ms,
            Measurement.packet_loss_pct,
            Measurement.quality_status,
            Measurement.connection_status,
            Measurement.iface_type,
            Measurement.duration_s,
            Measurement.external_ip,
            Measurement.server,
            Measurement.agent_version,
            Measurement.source,
        )
        .select_from(Measurement)
        .join(Line, Line.id == Measurement.line_id)
        .join(School, School.id == Line.school_id)
        .outerjoin(Device, Device.id == Measurement.device_id)
        .outerjoin(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(
            Measurement.measured_at >= body.period_from,
            Measurement.measured_at < body.period_to,
        )
        .order_by(School.full_name, School.id, Measurement.measured_at, Measurement.id)
    )
    if body.school_ids:
        query = query.where(School.id.in_(body.school_ids))
    if body.device_ids:
        query = query.where(Measurement.device_id.in_(body.device_ids))
    if body.statuses:
        query = query.where(Measurement.quality_status.in_(body.statuses))
    return query


async def raw_count(session: AsyncSession, body: ExportCreate) -> int:
    """Rows the raw file of ``body`` would have: what decides between the request and Celery."""
    rows = raw_query(body).order_by(None).subquery()
    return await session.scalar(select(func.count()).select_from(rows)) or 0


async def raw_records(
    session: AsyncSession, body: ExportCreate, zone: tzinfo
) -> list[dict[str, Any]]:
    """Every column of every measurement of the selection, keyed by the column codes, as JSON
    has them: codes, ISO date and time; ordered by school, then time."""
    records = []
    for row in await session.execute(raw_query(body)):
        local = row.measured_at.astimezone(zone)
        records.append(
            {
                "school_name": row.full_name,
                "hostname": row.hostname,
                "room": row.room,
                "date": local.date().isoformat(),
                "time": local.time().replace(microsecond=0).isoformat(),
                "download_mbps": row.download_mbps,
                "upload_mbps": row.upload_mbps,
                "ping_ms": row.ping_ms,
                "jitter_ms": row.jitter_ms,
                "packet_loss_pct": row.packet_loss_pct,
                "quality_status": row.quality_status,
                "school_code": row.school_code,
                "device_id": row.device_id,
                "line_status": row.line_status,
                "connection_status": row.connection_status,
                "iface_type": row.iface_type,
                "duration_s": row.duration_s,
                "external_ip": None if row.external_ip is None else str(row.external_ip),
                "server": row.server,
                "agent_version": row.agent_version,
                "source": row.source,
            }
        )
    return records
