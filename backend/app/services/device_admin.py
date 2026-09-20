"""Devices in the admin panel (T-36, ТЗ п. 12, п. 20): installation codes, the list, rebinding,
blocking and the token rotation (ADR-005).

An installation code is shown once: the row keeps its argon2 hash, the code starts with the id
of the row so that registration finds it (``app/core/security.py``). Its lifetime is
``enrollment_code_ttl_days`` of the system settings, never a constant (ТЗ п. 20).

Blocking and rebinding keep the device and its measurements: a measurement stores the line it
went through, so the history stays where it was taken (ТЗ п. 16, п. 20). The update channel of a
device is set here too: a computer on ``pilot`` installs a release before the rest (T-50).

Token rotation is delivered by the agent itself (ADR-005 leaves the order to T-36): the panel
only sets ``token_rotation_requested_at``; the agent sees ``token_rotation_required`` in
``GET /api/agent/config`` and calls ``POST /api/agent/token`` with its current token, which
answers a new one and makes the old one stop working at once. The server never keeps a token it
has not handed out. An agent that loses the answer is left without a valid token and registers
again with a new installation code of its school, keeping its history (``register_device``).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.security import (
    format_device_token,
    format_enrollment_code,
    hash_secret,
    new_device_secret,
    new_enrollment_secret,
)
from app.models import Device, EnrollmentCode, MonitoringPoint, School
from app.schemas.devices import DeviceDetailPage, DeviceUpdate, EnrollmentCodeIssued
from app.schemas.statuses import DeviceStatus
from app.services.device_card import device_detail_rows, device_details, device_not_found
from app.services.references import Changes, apply_changes, invalid_field, matching, page_of
from app.services.settings import system_settings


async def issue_enrollment_code(
    session: AsyncSession, school_id: int
) -> tuple[EnrollmentCodeIssued, int]:
    """One-time installation code of a school in the user's scope and the id of its row, which
    the audit record names instead of the code; 422 on an unknown school."""
    if await session.scalar(select(School.id).where(School.id == school_id)) is None:
        raise invalid_field("school_id", "Школа не найдена")
    settings = await system_settings(session)
    secret = new_enrollment_secret()
    entry = EnrollmentCode(
        code_hash=hash_secret(secret),
        school_id=school_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.enrollment_code_ttl_days),
    )
    session.add(entry)
    await session.flush()
    issued = EnrollmentCodeIssued(
        code=format_enrollment_code(entry.id, secret),
        school_id=school_id,
        expires_at=entry.expires_at,
    )
    await session.commit()
    return issued, entry.id


async def device_list(
    session: AsyncSession,
    params: PageParams,
    *,
    school_id: int | None,
    status: DeviceStatus | None,
    q: str | None,
    now: datetime,
) -> DeviceDetailPage:
    """Devices of the user's scope, by school and computer name."""
    query = device_detail_rows()
    if school_id is not None:
        query = query.where(MonitoringPoint.school_id == school_id)
    if status is not None:
        query = query.where(Device.status == status)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Device.hostname.ilike(pattern),
                *matching(q, Device.device_uid, School.full_name, School.school_code),
            )
        )
    rows, total = await page_of(
        session, query.order_by(School.full_name, MonitoringPoint.name, Device.id), params
    )
    return DeviceDetailPage(
        items=await device_details(session, rows, now=now),
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def scoped_device(session: AsyncSession, device_id: int) -> Device:
    """Device in the user's scope for a change; 404 outside it (ADR-008)."""
    device = await session.scalar(
        select(Device)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(Device.id == device_id)
    )
    if device is None:
        raise device_not_found()
    return device


async def update_device(session: AsyncSession, device_id: int, body: DeviceUpdate) -> Changes:
    """Bind the device to another point, possibly of another school, and set the channel its
    agent updates from (T-50); 422 on an unknown point."""
    device = await scoped_device(session, device_id)
    updates = body.model_dump(exclude_unset=True)
    point_id = updates.get("monitoring_point_id")
    if point_id is not None:
        point = await session.scalar(
            select(MonitoringPoint.id).where(MonitoringPoint.id == point_id)
        )
        if point is None:
            raise invalid_field("monitoring_point_id", "Точка мониторинга не найдена")
    changes = apply_changes(device, updates)
    await session.commit()
    return changes


async def set_device_status(session: AsyncSession, device_id: int, status: DeviceStatus) -> None:
    """Block or unblock: a blocked agent gets 403 on every request, nothing is deleted."""
    device = await scoped_device(session, device_id)
    device.status = status
    await session.commit()


async def request_token_rotation(session: AsyncSession, device_id: int) -> Changes:
    """Ask the agent for a new token; a pending request keeps its first moment."""
    device = await scoped_device(session, device_id)
    changes: Changes = {}
    if device.token_rotation_requested_at is None:
        device.token_rotation_requested_at = datetime.now(UTC)
        changes["token_rotation"] = {"old": None, "new": "requested"}
    await session.commit()
    return changes


async def rotate_token(session: AsyncSession, device: Device) -> str:
    """New token of the device; the old one stops working with this commit (ADR-005)."""
    secret = new_device_secret()
    device.token_hash = hash_secret(secret)
    device.token_rotation_requested_at = None
    await session.commit()
    return format_device_token(device.id, secret)
