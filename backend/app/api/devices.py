"""Device API of the panel (plan.md §10 «Устройства»): card, measurement history, blocking,
installation codes.

Endpoints of later tasks answer 501 until the task in ``not_implemented`` lands. The card and
the history are limited by the user's scope (ADR-008); a device outside it is a 404.
Agent endpoints under ``/devices`` (register, heartbeat) live in ``agent.py``. Blocking keeps
the device and its measurements (ADR-005).
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.core.errors import not_implemented
from app.schemas.devices import (
    DeviceDetail,
    EnrollmentCodeCreate,
    EnrollmentCodeIssued,
    MeasurementListItemPage,
)
from app.schemas.errors import Problem
from app.services.device_card import device_detail, device_measurements

router = APIRouter(
    prefix="/devices", tags=["devices"], dependencies=[Depends(require("devices:read"))]
)

DEVICE_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Устройство не найдено"}


@router.post(
    "/enrollment-codes",
    dependencies=[Depends(require("devices:manage"))],
    status_code=status.HTTP_201_CREATED,
    summary="Выдать одноразовый код установки агента для школы",
    description="Неизвестный school_id — 422.",
)
async def create_enrollment_code(body: EnrollmentCodeCreate) -> EnrollmentCodeIssued:
    raise not_implemented("T-36")


@router.get(
    "/{device_id}",
    summary="Карточка устройства",
    responses={404: DEVICE_NOT_FOUND},
)
async def get_device(
    device_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> DeviceDetail:
    return await device_detail(session, device_id, now=datetime.now(UTC))


@router.get(
    "/{device_id}/measurements",
    summary="История замеров устройства, новые сверху",
    responses={404: DEVICE_NOT_FOUND},
)
async def list_device_measurements(
    device_id: int,
    params: Annotated[PageParams, Depends(page_params)],
    period_from: Annotated[
        AwareDatetime | None, Query(description="Начало периода по measured_at, включительно")
    ] = None,
    period_to: Annotated[
        AwareDatetime | None, Query(description="Конец периода по measured_at, не включается")
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeasurementListItemPage:
    return await device_measurements(
        session, device_id, params, period_from=period_from, period_to=period_to
    )


@router.post(
    "/{device_id}/block",
    dependencies=[Depends(require("devices:manage"))],
    summary="Заблокировать устройство: запросы агента отклоняются, история остаётся",
    responses={404: DEVICE_NOT_FOUND},
)
async def block_device(device_id: int) -> DeviceDetail:
    raise not_implemented("T-36")


@router.post(
    "/{device_id}/unblock",
    dependencies=[Depends(require("devices:manage"))],
    summary="Разблокировать устройство",
    responses={404: DEVICE_NOT_FOUND},
)
async def unblock_device(device_id: int) -> DeviceDetail:
    raise not_implemented("T-36")
