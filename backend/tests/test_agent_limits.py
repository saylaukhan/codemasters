"""T-51: ranges the numbers of an agent must fit into and the limit on how often it may call.

A value outside its range and a moment outside the window of the queue are refused with
problem+json naming the field (ADR-009); requests over the limit get 429 with ``Retry-After``,
and the first of them is written to the audit log as a transfer error (ТЗ п. 12, T-39).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AuditLog
from app.schemas.agent import MAX_QUEUE_AGE, MAX_SPEED_MBPS
from tests.conftest import MemoryCounter
from tests.factories import create_school, primary_point, register_device
from tests.test_agent_measurements import agent, count, measurement
from tests.test_agent_register import as_device, heartbeat, problem

MEASUREMENTS = "/api/measurements"
BATCH = "/api/measurements/batch"
OUTAGES = "/api/outages"
REGISTER = "/api/devices/register"
HEARTBEAT = "/api/devices/heartbeat"


def fields(body: dict[str, Any]) -> dict[str, str]:
    """``errors[]`` of a validation problem as ``{field: message}`` (ADR-009)."""
    return {error["field"]: error["message"] for error in body["errors"]}


@pytest.fixture
def narrow_limit(monkeypatch: pytest.MonkeyPatch) -> int:
    """Two requests per window instead of the hundred of the settings: a test is not a flood."""
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_rate_limit", 2)
    monkeypatch.setattr(settings, "agent_register_rate_limit", 2)
    return 2


async def test_speed_below_zero_and_loss_over_a_hundred_are_refused_by_field(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)

    response = await api_client.post(
        MEASUREMENTS,
        json=measurement(download_mbps=-1, packet_loss_pct=100.5),
        headers=as_device(token),
    )

    body = problem(response, 422, "validation_error")
    assert fields(body) == {
        "download_mbps": "Значение должно быть не меньше 0.0",
        "packet_loss_pct": "Значение должно быть не больше 100.0",
    }
    assert await count(session) == 0


async def test_a_speed_above_the_range_is_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)

    response = await api_client.post(
        MEASUREMENTS,
        json=measurement(upload_mbps=MAX_SPEED_MBPS + 1),
        headers=as_device(token),
    )

    body = problem(response, 422, "validation_error")
    assert fields(body) == {"upload_mbps": f"Значение должно быть не больше {MAX_SPEED_MBPS}"}


async def test_the_borders_of_the_ranges_are_stored(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Линия, лежащая полностью, — это 0 и 100 %, а не ошибка агента."""
    _, token, _ = await agent(session)
    body = measurement(
        connection_status="offline",
        download_mbps=0,
        upload_mbps=MAX_SPEED_MBPS,
        ping_ms=0,
        packet_loss_pct=100,
    )

    response = await api_client.post(MEASUREMENTS, json=body, headers=as_device(token))

    assert response.status_code == 201, response.text
    assert await count(session) == 1


async def test_the_batch_names_the_item_out_of_range(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)
    items = [measurement(), measurement(ping_ms=-0.5), measurement()]

    response = await api_client.post(BATCH, json={"items": items}, headers=as_device(token))

    body = problem(response, 422, "validation_error")
    assert fields(body) == {"items[1].ping_ms": "Значение должно быть не меньше 0.0"}
    # One invalid record rejects the whole request: nothing of the batch is stored (ADR-006).
    assert await count(session) == 0


@pytest.mark.parametrize(
    ("shift", "message"),
    [
        (timedelta(hours=1), "Момент в будущем: проверьте часы компьютера"),
        (
            -MAX_QUEUE_AGE - timedelta(days=1),
            f"Момент старше срока очереди агента: {MAX_QUEUE_AGE.days} сут.",
        ),
    ],
    ids=["future", "older-than-the-queue"],
)
async def test_measured_at_outside_the_window_of_the_queue_is_refused(
    session: AsyncSession, api_client: AsyncClient, shift: timedelta, message: str
) -> None:
    _, token, _ = await agent(session)
    moment = datetime.now(UTC) + shift

    response = await api_client.post(
        MEASUREMENTS, json=measurement(measured_at=moment.isoformat()), headers=as_device(token)
    )

    body = problem(response, 422, "validation_error")
    assert fields(body) == {"measured_at": message}
    assert await count(session) == 0


async def test_a_measurement_resent_from_a_month_of_queue_is_stored(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Школа без связи месяц досылает очередь: это работа агента, а не мусор (ADR-006)."""
    _, token, _ = await agent(session)
    moment = datetime.now(UTC) - timedelta(days=29)

    response = await api_client.post(
        MEASUREMENTS, json=measurement(measured_at=moment.isoformat()), headers=as_device(token)
    )

    assert response.status_code == 201, response.text


async def test_an_outage_outside_the_window_of_the_queue_is_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)
    started_at = datetime.now(UTC) - MAX_QUEUE_AGE - timedelta(days=1)
    body = {
        "started_at": started_at.isoformat(),
        "ended_at": (started_at + timedelta(minutes=5)).isoformat(),
    }

    response = await api_client.post(OUTAGES, json=body, headers=as_device(token))

    assert set(fields(problem(response, 422, "validation_error"))) == {"started_at", "ended_at"}


async def test_requests_over_the_limit_are_refused_with_retry_after(
    session: AsyncSession, api_client: AsyncClient, narrow_limit: int
) -> None:
    _, token, _ = await agent(session)
    headers = as_device(token)

    allowed = [
        await api_client.post(HEARTBEAT, json=heartbeat(), headers=headers)
        for _ in range(narrow_limit)
    ]
    refused = await api_client.post(HEARTBEAT, json=heartbeat(), headers=headers)

    assert [response.status_code for response in allowed] == [204] * narrow_limit
    problem(refused, 429, "too_many_requests")
    # The agent waits the pause out instead of hammering the server (agent/internal/api/retry.go).
    assert refused.headers["Retry-After"] == str(get_settings().agent_rate_limit_window_s)


async def test_the_limit_counts_devices_apart(
    session: AsyncSession, api_client: AsyncClient, narrow_limit: int
) -> None:
    """Один разговорчивый агент не должен отрезать от сервера соседнюю школу."""
    _, token, _ = await agent(session)
    neighbour = await create_school(session, school_code="VKO-UK-002")
    _, other = await register_device(
        session, await primary_point(session, neighbour), device_uid="PC-2"
    )
    for _ in range(narrow_limit + 1):
        await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(token))

    response = await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(other))

    assert response.status_code == 204, response.text


async def test_the_first_refusal_of_a_window_is_written_to_the_audit_log(
    session: AsyncSession, api_client: AsyncClient, narrow_limit: int
) -> None:
    device, token, _ = await agent(session)
    for _ in range(narrow_limit + 3):
        await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(token))

    records = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "transfer_error"))
    ).all()

    # One record per window: the limit is there to stop a flood, not to turn it into a flood
    # of records (ТЗ п. 12, T-39).
    assert len(records) == 1
    assert records[0].error_type == "too_many_requests"
    assert records[0].entity_id == device.id


async def test_registration_is_limited_by_address(
    api_client: AsyncClient, narrow_limit: int
) -> None:
    """Регистрация идёт без токена: лимит по адресу защищает коды установки от перебора."""
    body = {
        "enrollment_code": "VKO-0011-2QD4X-7F3K9",
        "device_uid": "pc-of-the-guess",
        "agent_version": "0.1.0",
    }

    responses: list[Response] = [
        await api_client.post(REGISTER, json=body) for _ in range(narrow_limit + 1)
    ]

    assert [response.status_code for response in responses[:-1]] == [400] * narrow_limit
    problem(responses[-1], 429, "too_many_requests")


async def test_a_counter_that_does_not_answer_lets_the_measurement_through(
    session: AsyncSession,
    api_client: AsyncClient,
    narrow_limit: int,
    rate_limit_counter: MemoryCounter,
) -> None:
    """Замер дороже счётчика: недоступный Redis не должен терять данные (ADR-006)."""
    _, token, _ = await agent(session)
    rate_limit_counter.fails = True

    responses = [
        await api_client.post(MEASUREMENTS, json=measurement(), headers=as_device(token))
        for _ in range(narrow_limit + 2)
    ]

    assert [response.status_code for response in responses] == [201] * (narrow_limit + 2)
