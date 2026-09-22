"""Device API of the panel (plan.md §10 «Устройства»): list, card, measurement history,
rebinding, blocking, installation codes and the token rotation (T-36).

Everything is limited by the user's scope (ADR-008); a device outside it is a 404. Agent
endpoints under ``/devices`` (register, heartbeat) and ``POST /api/agent/token`` live in
``agent.py``. Blocking and rebinding keep the device and its measurements (ADR-005); how a new
token reaches the agent is described in ``app/services/device_admin.py``.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.devices import (
    DeviceDetail,
    DeviceDetailPage,
    DeviceUpdate,
    EnrollmentCodeCreate,
    EnrollmentCodeIssued,
    MeasurementListItemPage,
)
from app.schemas.errors import Problem
from app.schemas.statuses import DeviceStatus
from app.services import device_admin
from app.services.device_card import device_detail, device_measurements

router = APIRouter(
    prefix="/devices", tags=["devices"], dependencies=[Depends(require("devices:read"))]
)

DEVICE_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Устройство не найдено"}


@router.get(
    "",
    summary="Список устройств с их школой, точкой и статусом",
    description="q ищет по имени ПК, device_uid, названию школы и School ID.",
)
async def list_devices(
    params: Annotated[PageParams, Depends(page_params)],
    school_id: int | None = None,
    status: DeviceStatus | None = None,
    q: str | None = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceDetailPage:
    return await device_admin.device_list(
        session, params, school_id=school_id, status=status, q=q, now=datetime.now(UTC)
    )


@router.post(
    "/enrollment-codes",
    dependencies=[Depends(require("devices:manage"))],
    status_code=status.HTTP_201_CREATED,
    summary="Выдать одноразовый код установки агента для школы",
    description=(
        "Код показывается один раз, в БД — только его хэш; срок — enrollment_code_ttl_days "
        "системных настроек. Неизвестный school_id — 422."
    ),
)
async def create_enrollment_code(
    body: EnrollmentCodeCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EnrollmentCodeIssued:
    issued, code_id = await device_admin.issue_enrollment_code(session, body.school_id)
    describe_action(
        request, entity_id=code_id, changes={"school_id": {"old": None, "new": body.school_id}}
    )
    return issued


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


@router.patch(
    "/{device_id}",
    dependencies=[Depends(require("devices:manage"))],
    summary="Перепривязать устройство и задать канал обновления агента",
    description=(
        "Школа и линия новых замеров берутся из новой точки; прежние замеры остаются со своей "
        "линией. Неизвестный monitoring_point_id — 422. update_channel pilot выдаёт агенту "
        "релиз раньше остальных (T-50)."
    ),
    responses={404: DEVICE_NOT_FOUND},
)
async def update_device(
    device_id: int,
    body: DeviceUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceDetail:
    changes = await device_admin.update_device(session, device_id, body)
    describe_action(request, changes=changes or None)
    return await device_detail(session, device_id, now=datetime.now(UTC))


@router.post(
    "/{device_id}/block",
    dependencies=[Depends(require("devices:manage"))],
    summary="Заблокировать устройство: запросы агента отклоняются, история остаётся",
    responses={404: DEVICE_NOT_FOUND},
)
async def block_device(
    device_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> DeviceDetail:
    await device_admin.set_device_status(session, device_id, "blocked")
    return await device_detail(session, device_id, now=datetime.now(UTC))


@router.post(
    "/{device_id}/unblock",
    dependencies=[Depends(require("devices:manage"))],
    summary="Разблокировать устройство",
    responses={404: DEVICE_NOT_FOUND},
)
async def unblock_device(
    device_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> DeviceDetail:
    await device_admin.set_device_status(session, device_id, "active")
    return await device_detail(session, device_id, now=datetime.now(UTC))


@router.post(
    "/{device_id}/token-rotation",
    dependencies=[Depends(require("devices:manage"))],
    summary="Запросить замену токена устройства",
    description=(
        "Токен здесь не выдаётся: агент видит token_rotation_required в GET /api/agent/config, "
        "вызывает POST /api/agent/token текущим токеном и получает новый; старый сразу "
        "перестаёт работать. Пока агент не забрал токен, token_rotation_requested_at заполнен. "
        "Агент, потерявший ответ, регистрируется заново новым кодом установки своей школы."
    ),
    responses={404: DEVICE_NOT_FOUND},
)
async def request_token_rotation(
    device_id: int, request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> DeviceDetail:
    changes = await device_admin.request_token_rotation(session, device_id)
    describe_action(request, changes=changes or None)
    return await device_detail(session, device_id, now=datetime.now(UTC))


@router.post(
    "/{device_id}/measure",
    dependencies=[Depends(require("devices:manage"))],
    summary="Запросить внеплановый замер",
    description=(
        "Замер здесь не выполняется: агент видит measure_requested_at в ответе на POST "
        "/api/devices/heartbeat, делает один замер и присылает его как обычно, не дожидаясь "
        "слота. Расписание устройства не меняется (ТЗ п. 2). Пока замер не пришёл, "
        "measure_requested_at заполнен; запрос старше часа агенту не выдаётся, и повторное "
        "нажатие тогда создаёт новый."
    ),
    responses={404: DEVICE_NOT_FOUND},
)
async def request_measurement(
    device_id: int, request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> DeviceDetail:
    changes = await device_admin.request_measurement(session, device_id)
    describe_action(request, changes=changes or None)
    return await device_detail(session, device_id, now=datetime.now(UTC))
