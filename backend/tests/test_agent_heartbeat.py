"""T-16: heartbeat of an agent and the outages it reports (ТЗ п. 2, п. 3; ADR-006, ADR-014)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PROBLEM_MEDIA_TYPE
from app.models import Heartbeat, Line, Outage
from tests.factories import create_school, primary_point, register_device

HEARTBEAT = "/api/devices/heartbeat"
OUTAGES = "/api/outages"


def as_device(token: str) -> dict[str, str]:
    return {"Authorization": f"Device {token}"}


def beat(agent_version: str = "0.1.0") -> dict[str, Any]:
    return {"sent_at": datetime.now(UTC).isoformat(), "agent_version": agent_version}


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


async def test_heartbeat_marks_the_device_alive_and_remembers_its_version(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))

    first = await api_client.post(HEARTBEAT, json=beat("0.2.0"), headers=as_device(token))
    repeated = await api_client.post(HEARTBEAT, json=beat("0.2.0"), headers=as_device(token))

    assert (first.status_code, first.content) == (204, b"")
    assert repeated.status_code == 204
    await session.refresh(device)
    assert device.agent_version == "0.2.0"
    assert device.last_seen_at is not None
    assert abs(device.last_seen_at - datetime.now(UTC)) < timedelta(minutes=1)
    # Both requests share one transaction timestamp here, and one signal is one row.
    rows = (await session.execute(select(Heartbeat.device_id, Heartbeat.ts))).tuples().all()
    assert rows == [(device.id, device.last_seen_at)]


async def test_outage_is_stored_once_and_a_resent_one_is_a_conflict(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))
    started_at = datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
    outage = {
        "started_at": started_at.isoformat(),
        "ended_at": (started_at + timedelta(minutes=20)).isoformat(),
    }

    accepted = await api_client.post(OUTAGES, json=outage, headers=as_device(token))
    resent = await api_client.post(OUTAGES, json=outage, headers=as_device(token))
    later = await api_client.post(
        OUTAGES,
        json={
            "started_at": (started_at + timedelta(hours=1)).isoformat(),
            "ended_at": (started_at + timedelta(hours=1, minutes=5)).isoformat(),
        },
        headers=as_device(token),
    )

    assert accepted.status_code == 201, accepted.text
    problem(resent, 409, "duplicate_outage")
    assert later.status_code == 201, later.text
    stored = (await session.scalars(select(Outage).order_by(Outage.started_at))).all()
    line_id = await session.scalar(select(Line.id).where(Line.school_id == school.id))
    # The line comes from the monitoring point of the device, never from the body (ТЗ п. 12).
    assert [(row.id, row.device_id, row.line_id) for row in stored] == [
        (accepted.json()["id"], device.id, line_id),
        (later.json()["id"], device.id, line_id),
    ]


async def test_heartbeat_and_outages_need_the_device_token(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))
    device.status = "blocked"
    await session.flush()

    problem(await api_client.post(HEARTBEAT, json=beat()), 401, "unauthorized")
    problem(
        await api_client.post(HEARTBEAT, json=beat(), headers=as_device(token)),
        403,
        "device_blocked",
    )
    # A blocked device leaves no trace of being alive (ТЗ п. 16).
    assert (await session.scalars(select(Heartbeat.ts))).all() == []
