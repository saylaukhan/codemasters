"""Agent API (plan.md §10): registration, heartbeat, configuration, measurements, outages.

Contract stubs: every endpoint answers 501 until the task in ``not_implemented`` lands.
All endpoints except registration require ``Authorization: Device <token>`` (ADR-005).
"""

from typing import Annotated

from fastapi import APIRouter, Header, Security, status

from app.core.deps import device_token
from app.core.errors import not_implemented
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

router = APIRouter(tags=["agent"])
device_router = APIRouter(dependencies=[Security(device_token)])


@router.post(
    "/devices/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация устройства по коду установки",
    responses={
        400: {"model": Problem, "description": "Код просрочен, использован или не найден"},
    },
)
async def register_device(body: DeviceRegisterRequest) -> DeviceRegisterResponse:
    raise not_implemented("T-14")


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
