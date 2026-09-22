"""Device card of the panel (T-26, ТЗ п. 4, п. 6): the computer and its measurement history.

Every query runs in the session of the request, so RLS limits it to the user's scope: a device
outside it is «не найдено», not «запрещено» (ADR-008). The provider sees a device and its
measurements only on its own lines.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import Device, Measurement, MonitoringPoint, School
from app.schemas.agent import live_measure_request
from app.schemas.devices import DeviceDetail, MeasurementListItem, MeasurementListItemPage
from app.services.school_card import device_items, device_rows


def device_not_found() -> ApiError:
    return ApiError(404, "not_found", "Устройство не найдено")


def device_detail_rows() -> Select[Any]:
    """Rows of ``device_rows`` with the school of the device, for ``device_details``."""
    return (
        device_rows()
        .add_columns(School.school_code, School.full_name.label("school_name"))
        .join(School, School.id == MonitoringPoint.school_id)
    )


async def device_detail(session: AsyncSession, device_id: int, *, now: datetime) -> DeviceDetail:
    row = (await session.execute(device_detail_rows().where(Device.id == device_id))).one_or_none()
    if row is None:
        raise device_not_found()
    [detail] = await device_details(session, [row], now=now)
    return detail


async def device_details(
    session: AsyncSession, rows: Sequence[Any], *, now: datetime
) -> list[DeviceDetail]:
    """Rows of ``device_detail_rows`` as cards; shared by the card and the admin list (T-36)."""
    items = await device_items(session, rows, now=now)
    return [
        DeviceDetail.model_validate(
            {
                **item.model_dump(),
                "os": row.Device.os,
                "school_id": row.MonitoringPoint.school_id,
                "school_code": row.school_code,
                "school_name": row.school_name,
                "registered_at": row.Device.registered_at,
                "token_rotation_requested_at": row.Device.token_rotation_requested_at,
                # A request the agent will no longer be given is not shown as pending (T-79).
                "measure_requested_at": live_measure_request(row.Device.measure_requested_at, now),
            }
        )
        for item, row in zip(items, rows, strict=True)
    ]


async def device_measurements(
    session: AsyncSession,
    device_id: int,
    params: PageParams,
    *,
    period_from: datetime | None,
    period_to: datetime | None,
) -> MeasurementListItemPage:
    """Measurements of the device, newest first, with the thresholds each was evaluated with."""
    if await session.scalar(select(Device.id).where(Device.id == device_id)) is None:
        raise device_not_found()
    query = select(Measurement).where(Measurement.device_id == device_id)
    if period_from is not None:
        query = query.where(Measurement.measured_at >= period_from)
    if period_to is not None:
        query = query.where(Measurement.measured_at < period_to)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    measurements = await session.scalars(
        query.order_by(Measurement.measured_at.desc(), Measurement.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return MeasurementListItemPage(
        items=[
            MeasurementListItem.model_validate(measurement, from_attributes=True)
            for measurement in measurements
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
