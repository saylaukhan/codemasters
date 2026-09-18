"""Device card of the panel (T-26, ТЗ п. 4, п. 6): the computer and its measurement history.

Every query runs in the session of the request, so RLS limits it to the user's scope: a device
outside it is «не найдено», not «запрещено» (ADR-008). The provider sees a device and its
measurements only on its own lines.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import Device, Measurement, MonitoringPoint, School
from app.schemas.devices import DeviceDetail, MeasurementListItem, MeasurementListItemPage
from app.services.school_card import device_items, device_rows


def device_not_found() -> ApiError:
    return ApiError(404, "not_found", "Устройство не найдено")


async def device_detail(session: AsyncSession, device_id: int, *, now: datetime) -> DeviceDetail:
    row = (
        await session.execute(
            device_rows()
            .add_columns(School.school_code, School.full_name.label("school_name"))
            .join(School, School.id == MonitoringPoint.school_id)
            .where(Device.id == device_id)
        )
    ).one_or_none()
    if row is None:
        raise device_not_found()
    [item] = await device_items(session, [row], now=now)
    return DeviceDetail.model_validate(
        {
            **item.model_dump(),
            "os": row.Device.os,
            "school_id": row.MonitoringPoint.school_id,
            "school_code": row.school_code,
            "school_name": row.school_name,
            "registered_at": row.Device.registered_at,
        }
    )


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
