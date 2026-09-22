"""T-15: intake of measurements, one by one and by the batch of a resent queue (ADR-006).

A record is stored under the device of the token and the line of its monitoring point: fields
that look like a School ID in the body are not part of the contract and change nothing
(ТЗ п. 12, ADR-005). A repeat of a ``measurement_uuid`` answers 409 and stores nothing.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, Measurement, MonitoringPoint, School
from app.schemas.agent import MAX_BATCH_SIZE
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)
from tests.test_agent_register import as_device, heartbeat, problem

MEASUREMENTS = "/api/measurements"
BATCH = "/api/measurements/batch"
# Inside the window of the agent queue the schemas accept (30 days, ADR-006, T-51).
MEASURED_AT = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)


def measurement(**fields: Any) -> dict[str, Any]:
    """Body of one measurement; ``measurement_uuid`` is new unless the test fixes it."""
    return {
        "measurement_uuid": str(uuid4()),
        "measured_at": MEASURED_AT.isoformat(),
        "connection_status": "online",
        "download_mbps": 94.5,
        "upload_mbps": 88.1,
        "ping_ms": 12.0,
        "jitter_ms": 1.5,
        "packet_loss_pct": 0.0,
        "duration_s": 21.4,
        "external_ip": "192.0.2.15",
        "server": "librespeed https://speedtest.example.kz",
        "iface_type": "ethernet",
        "agent_version": "0.1.0",
    } | fields


async def stored(session: AsyncSession, measurement_uuid: str) -> Measurement:
    return (
        await session.scalars(
            select(Measurement).where(Measurement.measurement_uuid == UUID(measurement_uuid))
        )
    ).one()


async def count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Measurement)) or 0


async def agent(session: AsyncSession, **school: Any) -> tuple[Device, str, School]:
    """A registered device of a school, with the token its agent would carry."""
    created = await create_school(session, **school)
    device, token = await register_device(session, await primary_point(session, created))
    return device, token, created


async def test_measurement_is_stored_under_the_school_of_the_device(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    device, token, school = await agent(session)
    other = await create_school(session, school_code="VKO-UK-002")
    body = measurement(school_id=other.id, school_code=other.school_code, line_id=999)

    response = await api_client.post(MEASUREMENTS, json=body, headers=as_device(token))

    assert response.status_code == 201, response.text
    row = await stored(session, body["measurement_uuid"])
    assert row.device_id == device.id
    # School ID of the body is not in the contract and is ignored: the school comes from the
    # chain device → monitoring_points → lines → schools (ТЗ п. 12, ADR-005).
    school_id = await session.scalar(select(Line.school_id).where(Line.id == row.line_id))
    assert school_id == school.id
    point_line = await session.scalar(
        select(MonitoringPoint.line_id).where(MonitoringPoint.id == device.monitoring_point_id)
    )
    assert row.line_id == point_line
    assert (row.download_mbps, row.ping_ms, row.connection_status) == (94.5, 12.0, "online")
    assert row.measured_at == MEASURED_AT
    # received_at is the server clock: the gap to measured_at is the time in the offline queue.
    assert row.received_at > row.measured_at
    assert datetime.fromisoformat(response.json()["received_at"]) == row.received_at
    # The server judges the measurement on receipt; the rules themselves are tested in T-18
    # (tests/test_measurement_status.py). This line has no contract speeds, so contract_ok is empty.
    assert row.quality_status == "normal"
    assert row.thresholds_snapshot is not None
    assert row.contract_ok is None


async def test_repeat_of_the_same_uuid_answers_409_and_stores_nothing(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)
    body = measurement()

    first = await api_client.post(MEASUREMENTS, json=body, headers=as_device(token))
    repeat = await api_client.post(MEASUREMENTS, json=body, headers=as_device(token))
    # Same record, resent after the queue re-read it: another moment, the same uuid (T-02).
    later = measurement(
        measurement_uuid=body["measurement_uuid"],
        measured_at=(MEASURED_AT + timedelta(minutes=1)).isoformat(),
    )
    moved = await api_client.post(MEASUREMENTS, json=later, headers=as_device(token))

    assert first.status_code == 201, first.text
    problem(repeat, 409, "duplicate_measurement")
    problem(moved, 409, "duplicate_measurement")
    assert await count(session) == 1


async def test_batch_of_a_hundred_with_duplicates_is_accepted_whole(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)
    already = measurement()
    assert (
        await api_client.post(MEASUREMENTS, json=already, headers=as_device(token))
    ).status_code == 201
    items = [measurement() for _ in range(MAX_BATCH_SIZE - 3)]
    # The queue resends a record the server has, and repeats one record inside the batch.
    items.insert(7, already)
    items.insert(30, items[12])
    items.append(items[12])
    assert len(items) == MAX_BATCH_SIZE

    response = await api_client.post(BATCH, json={"items": items}, headers=as_device(token))

    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [result["measurement_uuid"] for result in results] == [
        item["measurement_uuid"] for item in items
    ]
    duplicates = {7, 30, MAX_BATCH_SIZE - 1}
    assert {index for index, result in enumerate(results) if result["status"] == 409} == duplicates
    assert all(results[index]["type"] == "duplicate_measurement" for index in duplicates)
    assert all(result["type"] is None for result in results if result["status"] == 201)
    # 100 items, three of them already known: 97 new rows next to the one sent before.
    assert await count(session) == MAX_BATCH_SIZE - 3 + 1


async def test_invalid_item_rejects_the_whole_batch(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token, _ = await agent(session)
    items = [measurement() for _ in range(5)]
    items[3]["ping_ms"] = "быстро"

    response = await api_client.post(BATCH, json={"items": items}, headers=as_device(token))

    body = problem(response, 422, "validation_error")
    assert body["errors"] == [{"field": "items[3].ping_ms", "message": "Ожидается число"}]
    assert await count(session) == 0


async def test_intake_needs_an_active_device(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    device, token, _ = await agent(session)

    without_token = await api_client.post(MEASUREMENTS, json=measurement())
    device.status = "blocked"
    await session.flush()
    blocked = await api_client.post(MEASUREMENTS, json=measurement(), headers=as_device(token))
    blocked_batch = await api_client.post(
        BATCH, json={"items": [measurement()]}, headers=as_device(token)
    )

    problem(without_token, 401, "unauthorized")
    problem(blocked, 403, "device_blocked")
    problem(blocked_batch, 403, "device_blocked")
    assert await count(session) == 0
    # The same token still fails on every other endpoint of the agent (ADR-005).
    problem(
        await api_client.post("/api/devices/heartbeat", json=heartbeat(), headers=as_device(token)),
        403,
        "device_blocked",
    )


async def test_the_source_of_a_measurement_is_stored_and_read_back(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """T-79: замер по расписанию и замер по кнопке различимы в истории; чужое значение — 422."""
    await create_settings(session)
    device, token, _ = await agent(session)
    admin = bearer(await create_user(session, "admin"))

    planned = measurement()
    asked = measurement(measured_at=datetime.now(UTC).isoformat(), source="manual")
    for body in (planned, asked):
        assert (
            await api_client.post(MEASUREMENTS, json=body, headers=as_device(token))
        ).status_code == 201

    # An agent older than T-79 sends no source at all, and its measurement is a planned one.
    assert "source" not in planned
    assert (await stored(session, planned["measurement_uuid"])).source == "schedule"
    assert (await stored(session, asked["measurement_uuid"])).source == "manual"

    history = await api_client.get(f"/api/devices/{device.id}/measurements", headers=admin)
    assert history.status_code == 200, history.text
    assert [(item["measurement_uuid"], item["source"]) for item in history.json()["items"]] == [
        (asked["measurement_uuid"], "manual"),
        (planned["measurement_uuid"], "schedule"),
    ]

    refused = problem(
        await api_client.post(
            MEASUREMENTS, json=measurement(source="by-hand"), headers=as_device(token)
        ),
        422,
        "validation_error",
    )
    assert [error["field"] for error in refused["errors"]] == ["source"]
