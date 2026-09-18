"""T-36: devices in the admin panel — installation codes, rebinding, blocking, token rotation.

A code is shown once and the database keeps only its hash (ADR-005); a blocked agent is refused
while its measurements stay (ТЗ п. 16, п. 20); a rotated token replaces the old one, which stops
working, and the agent learns about the rotation from its configuration. Every action of the
panel is audited, the code and the token never are.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import parse_enrollment_code, verify_secret
from app.models import AuditLog, Device, EnrollmentCode, Measurement
from tests.factories import (
    add_point,
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)
from tests.test_agent_measurements import measurement

CODES = "/api/devices/enrollment-codes"
HEARTBEAT = "/api/devices/heartbeat"
CONFIG = "/api/agent/config"
TOKEN = "/api/agent/token"


def ok(response: Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


def as_device(token: str) -> dict[str, str]:
    return {"Authorization": f"Device {token}"}


def beat() -> dict[str, Any]:
    return {"sent_at": datetime.now(UTC).isoformat(), "agent_version": "0.1.0"}


async def audit_records(session: AsyncSession, entity_type: str) -> list[tuple[Any, ...]]:
    """Records of panel actions; rejected agent requests (``transfer_error``) are left out."""
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == entity_type, AuditLog.action != "transfer_error")
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


async def test_an_installation_code_is_shown_once_and_registers_a_device(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    settings = await create_settings(session)
    settings.enrollment_code_ttl_days = 3
    school = await create_school(session)
    admin = bearer(await create_user(session, "admin"))

    issued = ok(await api_client.post(CODES, json={"school_id": school.id}, headers=admin), 201)

    assert issued["school_id"] == school.id
    expires_at = datetime.fromisoformat(issued["expires_at"])
    assert abs(expires_at - (datetime.now(UTC) + timedelta(days=3))) < timedelta(minutes=1)
    # The row keeps the hash of the random part only: the code itself is nowhere in it.
    parsed = parse_enrollment_code(issued["code"])
    assert parsed is not None
    entry = await session.get_one(EnrollmentCode, parsed[0])
    assert issued["code"] not in entry.code_hash and parsed[1] not in entry.code_hash
    assert verify_secret(parsed[1], entry.code_hash)
    assert entry.school_id == school.id and entry.used_at is None

    registered = ok(
        await api_client.post(
            "/api/devices/register",
            json={
                "enrollment_code": issued["code"],
                "device_uid": "PC-NEW",
                "agent_version": "0.1.0",
            },
        ),
        201,
    )
    assert registered["device_id"] > 0

    problem(
        await api_client.post(CODES, json={"school_id": 999_999}, headers=admin),
        422,
        "validation_error",
    )
    oblast = bearer(await create_user(session, "oblast"))
    problem(
        await api_client.post(CODES, json={"school_id": school.id}, headers=oblast),
        403,
        "forbidden",
    )

    records = await audit_records(session, "enrollment_code")
    assert records == [("create", entry.id, {"school_id": {"old": None, "new": school.id}})]


async def test_a_blocked_device_is_refused_and_keeps_its_history(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))
    ok(
        await api_client.post("/api/measurements", json=measurement(), headers=as_device(token)),
        201,
    )
    admin = bearer(await create_user(session, "admin"))

    blocked = ok(await api_client.post(f"/api/devices/{device.id}/block", headers=admin))
    assert blocked["status"] == "blocked"
    problem(
        await api_client.post(HEARTBEAT, json=beat(), headers=as_device(token)),
        403,
        "device_blocked",
    )
    listed = ok(await api_client.get("/api/devices", params={"status": "blocked"}, headers=admin))
    assert [item["id"] for item in listed["items"]] == [device.id]
    history = ok(await api_client.get(f"/api/devices/{device.id}/measurements", headers=admin))
    assert history["total"] == 1

    unblocked = ok(await api_client.post(f"/api/devices/{device.id}/unblock", headers=admin))
    assert unblocked["status"] == "active"
    assert (
        await api_client.post(HEARTBEAT, json=beat(), headers=as_device(token))
    ).status_code == 204
    assert await session.scalar(select(func.count()).select_from(Measurement)) == 1

    district = bearer(await create_user(session, "district", region_id=school.region_id))
    problem(
        await api_client.post(f"/api/devices/{device.id}/block", headers=district), 403, "forbidden"
    )
    problem(await api_client.post("/api/devices/999999/block", headers=admin), 404, "not_found")
    records = await audit_records(session, "device")
    assert [(action, entity_id) for action, entity_id, _ in records] == [
        ("block", device.id),
        ("unblock", device.id),
    ]


async def test_a_device_is_rebound_to_a_point_of_another_school(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    old_point = await primary_point(session, school)
    other = await create_school(session, school_code="VKO-UK-002")
    new_point = await add_point(session, other, name="Кабинет информатики", room="204")
    device, token = await register_device(session, old_point)
    ok(
        await api_client.post("/api/measurements", json=measurement(), headers=as_device(token)),
        201,
    )
    admin = bearer(await create_user(session, "admin"))

    moved = ok(
        await api_client.patch(
            f"/api/devices/{device.id}",
            json={"monitoring_point_id": new_point.id},
            headers=admin,
        )
    )

    assert (moved["school_id"], moved["monitoring_point_id"]) == (other.id, new_point.id)
    assert moved["room"] == "204"
    # The measurement taken before keeps the line it went through.
    old_line = await session.scalar(select(Measurement.line_id))
    assert old_line == old_point.line_id
    problem(
        await api_client.patch(
            f"/api/devices/{device.id}", json={"monitoring_point_id": 999_999}, headers=admin
        ),
        422,
        "validation_error",
    )
    records = await audit_records(session, "device")
    assert records == [
        (
            "update",
            device.id,
            {"monitoring_point_id": {"old": old_point.id, "new": new_point.id}},
        )
    ]


async def test_a_rotated_token_replaces_the_old_one(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, old_token = await register_device(session, await primary_point(session, school))
    admin = bearer(await create_user(session, "admin"))

    before = await api_client.get(CONFIG, headers=as_device(old_token))
    assert ok(before)["token_rotation_required"] is False

    requested = ok(await api_client.post(f"/api/devices/{device.id}/token-rotation", headers=admin))
    assert requested["token_rotation_requested_at"] is not None
    # The request changes the configuration, so a cached one is fetched again.
    config = await api_client.get(
        CONFIG, headers=as_device(old_token) | {"If-None-Match": before.headers["ETag"]}
    )
    assert ok(config)["token_rotation_required"] is True

    rotated = ok(await api_client.post(TOKEN, headers=as_device(old_token)))
    new_token = rotated["device_token"]
    assert rotated["device_id"] == device.id and new_token != old_token

    problem(
        await api_client.post(HEARTBEAT, json=beat(), headers=as_device(old_token)),
        401,
        "unauthorized",
    )
    problem(await api_client.post(TOKEN, headers=as_device(old_token)), 401, "unauthorized")
    assert (
        await api_client.post(HEARTBEAT, json=beat(), headers=as_device(new_token))
    ).status_code == 204
    assert (
        ok(await api_client.get(CONFIG, headers=as_device(new_token)))["token_rotation_required"]
        is False
    )
    card = ok(await api_client.get(f"/api/devices/{device.id}", headers=admin))
    assert card["token_rotation_requested_at"] is None
    assert (await session.get_one(Device, device.id)).token_rotation_requested_at is None

    # No token gets into the log: the request is an update with the fact of the rotation.
    records = await audit_records(session, "device")
    assert records == [("update", device.id, {"token_rotation": {"old": None, "new": "requested"}})]
