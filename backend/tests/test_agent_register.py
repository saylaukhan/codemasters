"""T-14: registration by a one-time installation code, device tokens, blocking (ADR-005).

The school of a device is never taken from the request: it comes from the code, and the point
the device is bound to decides the line of every measurement later (ТЗ п. 12).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PROBLEM_MEDIA_TYPE
from app.core.security import TOKEN_HASH_PREFIX, hash_secret, parse_device_token, verify_token
from app.models import Device, EnrollmentCode
from tests.factories import (
    add_point,
    create_school,
    issue_enrollment_code,
    primary_point,
    register_device,
)

REGISTER = "/api/devices/register"
HEARTBEAT = "/api/devices/heartbeat"


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    """Assert an ``application/problem+json`` answer with a stable ``type`` (ADR-009)."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


def registration(code: str, **fields: Any) -> dict[str, Any]:
    return {"enrollment_code": code, "device_uid": "PC-1", "agent_version": "0.1.0"} | fields


def heartbeat() -> dict[str, Any]:
    return {"sent_at": datetime.now(UTC).isoformat(), "agent_version": "0.1.0"}


def as_device(token: str) -> dict[str, str]:
    return {"Authorization": f"Device {token}"}


async def test_valid_code_creates_a_device_and_returns_a_token_once(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    code = await issue_enrollment_code(session, school)

    response = await api_client.post(
        REGISTER, json=registration(code, hostname="lab-01", os="Windows 11")
    )

    assert response.status_code == 201, response.text
    body = response.json()
    device = await session.get_one(Device, body["device_id"])
    assert (device.device_uid, device.hostname, device.os) == ("PC-1", "lab-01", "Windows 11")
    assert device.status == "active"
    # The school comes from the code: the device hangs on the point of that school (ADR-005).
    assert device.monitoring_point_id == (await primary_point(session, school)).id
    # The token itself is nowhere in the database, only its hash (ТЗ п. 12), and the hash
    # says which algorithm made it (``app/core/security.py``).
    device_id, secret = parse_device_token(body["device_token"]) or (0, "")
    assert device_id == device.id
    assert device.token_hash.startswith(TOKEN_HASH_PREFIX)
    assert secret not in device.token_hash
    assert verify_token(secret, device.token_hash)
    # The code is one-time: it is spent by this registration.
    spent = (await session.scalars(select(EnrollmentCode))).one()
    assert spent.used_at is not None


async def test_token_of_the_device_opens_the_agent_api(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))

    accepted = await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(token))
    without = await api_client.post(HEARTBEAT, json=heartbeat())
    wrong_secret = await api_client.post(
        HEARTBEAT, json=heartbeat(), headers=as_device(f"{device.id}.not-the-right-secret")
    )
    unknown_device = await api_client.post(
        HEARTBEAT, json=heartbeat(), headers=as_device("999999.not-the-right-secret")
    )
    # An id past the range of a bigint never reaches the database as a query parameter.
    beyond_bigint = await api_client.post(
        HEARTBEAT, json=heartbeat(), headers=as_device("9999999999999999999.not-the-right-secret")
    )
    wrong_scheme = await api_client.post(
        HEARTBEAT, json=heartbeat(), headers={"Authorization": f"Bearer {token}"}
    )

    # Authentication passed: the heartbeat of T-16 answers without a body.
    assert accepted.status_code == 204, accepted.text
    for refused in (without, wrong_secret, unknown_device, beyond_bigint, wrong_scheme):
        assert problem(refused, 401, "unauthorized")["detail"]
        assert refused.headers["www-authenticate"] == "Device"


async def test_token_hashed_by_argon2_is_accepted_and_upgraded(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """A device registered before the token left argon2 keeps working, and pays argon2 once.

    Its token was handed out once and never stored, so no migration could rehash the row: the
    agent brings the token back on its first request and the row is upgraded then
    (``app/core/deps.py``). A wrong secret must still be 401 and must change nothing.
    """
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))
    _, secret = parse_device_token(token) or (0, "")
    device.token_hash = hash_secret(secret)
    await session.flush()

    accepted = await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(token))
    await session.refresh(device)
    upgraded = device.token_hash
    wrong_secret = await api_client.post(
        HEARTBEAT, json=heartbeat(), headers=as_device(f"{device.id}.not-the-right-secret")
    )
    again = await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(token))

    assert accepted.status_code == 204, accepted.text
    assert again.status_code == 204, again.text
    problem(wrong_secret, 401, "unauthorized")
    # The row now holds the new format, and it is the hash of the same token as before.
    assert upgraded.startswith(TOKEN_HASH_PREFIX)
    assert verify_token(secret, upgraded)
    await session.refresh(device)
    assert device.token_hash == upgraded


async def test_blocked_device_is_refused_on_every_request(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))
    device.status = "blocked"
    await session.flush()
    code = await issue_enrollment_code(session, school)

    beat = await api_client.post(HEARTBEAT, json=heartbeat(), headers=as_device(token))
    again = await api_client.post(REGISTER, json=registration(code, device_uid=device.device_uid))

    problem(beat, 403, "device_blocked")
    problem(again, 403, "device_blocked")
    # Blocking keeps the device and its history, and the refused registration kept the code.
    await session.refresh(device)
    assert device.status == "blocked"
    assert (await session.scalars(select(EnrollmentCode.used_at))).all() == [None]


async def test_expired_used_and_unknown_codes_are_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    expired = await issue_enrollment_code(session, school, expires_in=timedelta(days=-1))
    code = await issue_enrollment_code(session, school)
    mistyped = await issue_enrollment_code(session, school)
    mistyped = mistyped[:-1] + ("2" if mistyped[-1] != "2" else "3")

    accepted = await api_client.post(REGISTER, json=registration(code))
    answers = {
        "expired_enrollment_code": await api_client.post(REGISTER, json=registration(expired)),
        "used_enrollment_code": await api_client.post(
            REGISTER, json=registration(code, device_uid="PC-2")
        ),
        "invalid_enrollment_code": await api_client.post(REGISTER, json=registration(mistyped)),
    }
    unknown = await api_client.post(REGISTER, json=registration("VKO-ZZZZ-ZZZZZ-ZZZZZ"))
    nonsense = await api_client.post(REGISTER, json=registration("не код"))

    assert accepted.status_code == 201, accepted.text
    for type_, response in answers.items():
        problem(response, 400, type_)
    problem(unknown, 400, "invalid_enrollment_code")
    problem(nonsense, 400, "invalid_enrollment_code")
    # Only the one accepted registration left a device behind.
    assert len((await session.scalars(select(Device))).all()) == 1


async def test_room_of_the_installer_chooses_the_point(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session, room="Серверная")
    lab = await add_point(session, school, name="Кабинет информатики", room="Кабинет 12")
    code = await issue_enrollment_code(session, school)
    other = await issue_enrollment_code(session, school)

    by_room = await api_client.post(REGISTER, json=registration(code, room=" кабинет  12 "))
    without_room = await api_client.post(REGISTER, json=registration(other, device_uid="PC-2"))

    assert by_room.status_code == 201, by_room.text
    assert (
        await session.get_one(Device, by_room.json()["device_id"])
    ).monitoring_point_id == lab.id
    # No room, or a room nobody knows: the primary point of the school (ТЗ п. 10).
    fallback = await session.get_one(Device, without_room.json()["device_id"])
    assert fallback.monitoring_point_id == (await primary_point(session, school)).id


async def test_computer_that_lost_its_token_registers_again(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    other_school = await create_school(session, school_code="VKO-UK-002")
    first = await api_client.post(
        REGISTER, json=registration(await issue_enrollment_code(session, school))
    )
    code = await issue_enrollment_code(session, school)
    stranger = await issue_enrollment_code(session, other_school)

    again = await api_client.post(REGISTER, json=registration(code))
    moved = await api_client.post(REGISTER, json=registration(stranger))
    old_token = await api_client.post(
        HEARTBEAT, json=heartbeat(), headers=as_device(first.json()["device_token"])
    )

    assert again.status_code == 201, again.text
    # The same row keeps its history; only the token is new (ADR-005).
    assert again.json()["device_id"] == first.json()["device_id"]
    assert again.json()["device_token"] != first.json()["device_token"]
    assert len((await session.scalars(select(Device))).all()) == 1
    problem(old_token, 401, "unauthorized")
    # A code of another school does not move the device there (ТЗ п. 12).
    problem(moved, 409, "device_registered_elsewhere")


async def test_school_without_a_monitoring_point_cannot_take_a_device(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session, with_point=False)
    code = await issue_enrollment_code(session, school)

    response = await api_client.post(REGISTER, json=registration(code))

    problem(response, 409, "no_monitoring_point")
    assert (await session.scalars(select(EnrollmentCode.used_at))).all() == [None]
