"""Agent API (plan.md §10): registration, heartbeat, configuration, measurements, outages.

All endpoints except registration require ``Authorization: Device <token>``: ``current_device``
answers 401 without a valid token and 403 for a blocked device (ADR-005). The school and the
line of a request are derived from the device binding, never taken from the body (ТЗ п. 12).
Endpoints still answering 501 name the task that implements them.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_device
from app.core.errors import ApiError, not_implemented
from app.core.security import (
    format_device_token,
    hash_secret,
    new_device_secret,
    parse_enrollment_code,
    verify_secret,
)
from app.models import Device, EnrollmentCode, MonitoringPoint
from app.schemas.agent import (
    AgentConfigResponse,
    AgentReleaseResponse,
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    HeartbeatRequest,
    MeasurementAccepted,
    MeasurementBatchRequest,
    MeasurementBatchResponse,
    MeasurementCreate,
    OutageAccepted,
    OutageCreate,
    WhoAmIResponse,
)
from app.schemas.errors import Problem

# Every endpoint of the agent but registration answers these two (ADR-005).
DEVICE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": Problem, "description": "Токен устройства отсутствует или недействителен"},
    403: {"model": Problem, "description": "Устройство заблокировано"},
}

router = APIRouter(tags=["agent"])
device_router = APIRouter(dependencies=[Depends(current_device)], responses=DEVICE_RESPONSES)

CODE_NOT_FOUND = "Код установки не найден"
BLOCKED = "Устройство заблокировано администратором"


@router.post(
    "/devices/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация устройства по коду установки",
    responses={
        400: {"model": Problem, "description": "Код просрочен, использован или не найден"},
        403: {"model": Problem, "description": "Устройство заблокировано"},
        409: {
            "model": Problem,
            "description": "Устройство зарегистрировано в другой школе или у школы нет точки",
        },
    },
)
async def register_device(
    body: DeviceRegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceRegisterResponse:
    """Exchange a one-time installation code for device credentials (ADR-005).

    The token is returned once and stored as an argon2 hash; the school comes from the code,
    the line from the monitoring point the device is bound to.
    """
    code = await valid_enrollment_code(session, body.enrollment_code)
    point = await binding_point(session, code.school_id, body.room)
    device = await device_to_register(session, body.device_uid, point)
    # Checks first, then the code is spent: a refused registration keeps the code usable.
    await spend_enrollment_code(session, code)

    secret = new_device_secret()
    device.monitoring_point_id = point.id
    device.hostname = body.hostname
    device.os = body.os
    device.agent_version = body.agent_version
    device.token_hash = hash_secret(secret)
    session.add(device)
    try:
        await session.flush()
    except IntegrityError as error:
        # Two agents registering the same device_uid at once: the second one loses the race.
        raise ApiError(
            409, "device_already_registered", "Устройство уже зарегистрировано"
        ) from error
    await session.commit()

    return DeviceRegisterResponse(
        device_id=device.id, device_token=format_device_token(device.id, secret)
    )


async def valid_enrollment_code(session: AsyncSession, code: str) -> EnrollmentCode:
    """Installation code that exists and has not expired; it is not spent yet (ADR-005)."""
    parsed = parse_enrollment_code(code)
    if parsed is None:
        raise ApiError(400, "invalid_enrollment_code", CODE_NOT_FOUND)
    code_id, secret = parsed
    entry = await session.get(EnrollmentCode, code_id)
    if entry is None or not verify_secret(secret, entry.code_hash):
        raise ApiError(400, "invalid_enrollment_code", CODE_NOT_FOUND)
    if entry.used_at is not None:
        raise ApiError(400, "used_enrollment_code", "Код установки уже использован")
    if entry.expires_at <= datetime.now(UTC):
        raise ApiError(400, "expired_enrollment_code", "Срок действия кода установки истёк")
    return entry


async def spend_enrollment_code(session: AsyncSession, entry: EnrollmentCode) -> None:
    """Mark the code used; the conditional UPDATE keeps it one-time under concurrency."""
    spent = await session.scalar(
        update(EnrollmentCode)
        .where(EnrollmentCode.id == entry.id, EnrollmentCode.used_at.is_(None))
        .values(used_at=func.now())
        .returning(EnrollmentCode.id)
    )
    if spent is None:
        raise ApiError(400, "used_enrollment_code", "Код установки уже использован")


def same_room(room: str | None, other: str | None) -> bool:
    """Rooms are written by hand: spacing and case must not make two of them different."""
    if room is None or other is None:
        return False
    return " ".join(room.split()).casefold() == " ".join(other.split()).casefold()


async def binding_point(session: AsyncSession, school_id: int, room: str | None) -> MonitoringPoint:
    """Point of the school the device measures from: the one in the room named by the installer,
    otherwise the primary point of the school (ТЗ п. 10, plan.md §4.1).

    A school has few points, so the room is matched in Python: ``lower()`` in the database
    depends on the collation of the cluster and would not fold Cyrillic under the C locale.
    """
    points = (
        await session.scalars(
            select(MonitoringPoint)
            .where(MonitoringPoint.school_id == school_id)
            .order_by(MonitoringPoint.is_primary.desc(), MonitoringPoint.id)
        )
    ).all()
    if not points:
        raise ApiError(
            409, "no_monitoring_point", "У школы нет точки мониторинга: создайте её в панели"
        )
    return next((point for point in points if same_room(room, point.room)), points[0])


async def device_to_register(
    session: AsyncSession, device_uid: str, point: MonitoringPoint
) -> Device:
    """New device, or the one that already carries this ``device_uid``.

    A computer that lost its token registers again with a new code of its own school and keeps
    its history; a code of another school does not move it, and a blocked device stays blocked
    (ТЗ п. 16, ADR-005).
    """
    device = await session.scalar(select(Device).where(Device.device_uid == device_uid))
    if device is None:
        return Device(device_uid=device_uid)
    if device.status != "active":
        raise ApiError(403, "device_blocked", BLOCKED)
    bound = await session.get_one(MonitoringPoint, device.monitoring_point_id)
    if bound.school_id != point.school_id:
        raise ApiError(
            409, "device_registered_elsewhere", "Устройство зарегистрировано в другой школе"
        )
    return device


@device_router.post(
    "/devices/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Сигнал «агент жив»",
)
async def send_heartbeat(body: HeartbeatRequest) -> None:
    raise not_implemented("T-16")


@device_router.get(
    "/agent/config",
    summary="Конфигурация агента: расписание, пороги, сервер замеров, версия",
    responses={
        200: {
            "headers": {
                "ETag": {"description": "Версия конфигурации", "schema": {"type": "string"}}
            }
        },
        304: {"description": "Конфигурация не изменилась: If-None-Match совпал с ETag"},
    },
)
async def get_agent_config(
    if_none_match: Annotated[str | None, Header()] = None,
) -> AgentConfigResponse:
    raise not_implemented("T-17")


@device_router.get("/agent/whoami", summary="Внешний IP запроса")
async def whoami() -> WhoAmIResponse:
    raise not_implemented("T-17")


@device_router.post(
    "/measurements",
    status_code=status.HTTP_201_CREATED,
    summary="Один замер",
    responses={
        409: {
            "model": Problem,
            "description": "Замер с этим measurement_uuid уже принят (type duplicate_measurement)",
        },
    },
)
async def create_measurement(body: MeasurementCreate) -> MeasurementAccepted:
    raise not_implemented("T-15")


@device_router.post(
    "/measurements/batch",
    summary="Досылка очереди: до 100 замеров, результат по каждому",
    description=(
        "Результат по каждой записи в порядке запроса: 201 — принята, 409 — уже была; оба "
        "означают «удалить из очереди». Невалидная запись отклоняет весь запрос с 422, "
        "её индекс — в errors[].field (`items[3].ping_ms`)."
    ),
)
async def create_measurement_batch(body: MeasurementBatchRequest) -> MeasurementBatchResponse:
    raise not_implemented("T-15")


@device_router.post(
    "/outages",
    status_code=status.HTTP_201_CREATED,
    summary="Простой, зафиксированный агентом",
    responses={
        409: {
            "model": Problem,
            "description": "Простой с этим started_at уже принят (type duplicate_outage)",
        },
    },
)
async def create_outage(body: OutageCreate) -> OutageAccepted:
    raise not_implemented("T-16")


@device_router.get(
    "/agent/releases/latest",
    summary="Последний релиз агента для обновления",
    responses={404: {"model": Problem, "description": "Релизов нет"}},
)
async def get_latest_agent_release() -> AgentReleaseResponse:
    raise not_implemented("T-50")


router.include_router(device_router)
