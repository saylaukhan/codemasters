"""T-50: agent releases and the self-update channel (ТЗ п. 20; plan.md §4.6; ADR-002).

The administrator publishes an MSI with its SHA-256 and a channel; a device on ``pilot`` takes
the build first and the rest only after it is promoted to ``stable``. A withdrawn release is
handed out to nobody, and a version is published once: a fix is a new release.
"""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRelease, AuditLog, Device, Provider, School
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

RELEASES = "/api/admin/agent-releases"
LATEST = "/api/agent/releases/latest"
CONFIG = "/api/agent/config"

STABLE = {
    "version": "0.2.0",
    "channel": "stable",
    "download_url": "https://monitor.example.kz/downloads/VKO-Agent-0.2.0.msi",
    "sha256": "a" * 64,
    "notes": "Первый релиз после пилота",
}
PILOT = {
    "version": "0.3.0",
    "channel": "pilot",
    "download_url": "https://monitor.example.kz/downloads/VKO-Agent-0.3.0.msi",
    "sha256": "b" * 64,
    "notes": None,
}


def ok(response: Response, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


def as_device(token: str) -> dict[str, str]:
    return {"Authorization": f"Device {token}"}


async def audit_records(session: AsyncSession, entity_type: str) -> list[tuple[Any, ...]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == entity_type, AuditLog.action != "transfer_error")
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


async def school_with_settings(session: AsyncSession) -> School:
    school = await create_school(session)
    await create_settings(session)
    return school


async def device_on(
    session: AsyncSession, school: School, *, device_uid: str, channel: str = "stable"
) -> tuple[Device, str]:
    """Device of the school on ``channel``, with its token; the channel is set by the panel."""
    device, token = await register_device(
        session, await primary_point(session, school), device_uid=device_uid
    )
    device.update_channel = channel
    await session.flush()
    return device, token


async def test_a_release_is_published_once_and_listed_newest_first(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))

    stable = ok(await api_client.post(RELEASES, json=STABLE, headers=admin), 201)
    pilot = ok(await api_client.post(RELEASES, json=PILOT, headers=admin), 201)
    repeated = problem(
        await api_client.post(RELEASES, json=STABLE | {"sha256": "c" * 64}, headers=admin),
        409,
        "release_version_taken",
    )

    assert stable == {
        "id": stable["id"],
        "is_active": True,
        "released_at": stable["released_at"],
        **STABLE,
    }
    assert repeated["detail"] == "Релиз с этой версией уже опубликован"
    listed = ok(await api_client.get(RELEASES, headers=admin))
    # The same version is never published twice, whatever hash the second attempt carries.
    assert listed["total"] == 2
    assert [item["version"] for item in listed["items"]] == ["0.3.0", "0.2.0"]
    assert await audit_records(session, "agent_release") == [
        ("create", stable["id"], None),
        ("create", pilot["id"], None),
    ]


async def test_a_release_is_promoted_and_withdrawn(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))
    pilot = ok(await api_client.post(RELEASES, json=PILOT, headers=admin), 201)

    promoted = ok(
        await api_client.patch(
            f"{RELEASES}/{pilot['id']}", json={"channel": "stable"}, headers=admin
        )
    )
    withdrawn = ok(
        await api_client.patch(
            f"{RELEASES}/{pilot['id']}", json={"is_active": False}, headers=admin
        )
    )
    missing = problem(
        await api_client.patch(f"{RELEASES}/999999", json={"is_active": False}, headers=admin),
        404,
        "not_found",
    )

    assert promoted["channel"] == "stable"
    assert withdrawn["is_active"] is False
    # The build itself never changes: only the channel and the withdrawal are editable.
    assert (withdrawn["version"], withdrawn["sha256"], withdrawn["download_url"]) == (
        PILOT["version"],
        PILOT["sha256"],
        PILOT["download_url"],
    )
    assert missing["detail"] == "Релиз агента не найден"
    assert await audit_records(session, "agent_release") == [
        ("create", pilot["id"], None),
        ("update", pilot["id"], {"channel": {"old": "pilot", "new": "stable"}}),
        ("update", pilot["id"], {"is_active": {"old": True, "new": False}}),
    ]


async def test_the_pilot_channel_gets_a_release_before_the_rest(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await school_with_settings(session)
    tester, pilot_token = await device_on(session, school, device_uid="PC-PILOT")
    _, stable_token = await device_on(session, school, device_uid="PC-1")
    admin = bearer(await create_user(session, "admin"))

    moved = ok(
        await api_client.patch(
            f"/api/devices/{tester.id}", json={"update_channel": "pilot"}, headers=admin
        )
    )
    ok(await api_client.post(RELEASES, json=STABLE, headers=admin), 201)
    pilot = ok(await api_client.post(RELEASES, json=PILOT, headers=admin), 201)

    assert moved["update_channel"] == "pilot"
    for_pilot = ok(await api_client.get(LATEST, headers=as_device(pilot_token)))
    for_stable = ok(await api_client.get(LATEST, headers=as_device(stable_token)))
    # The pilot computer gets the new build with its hash, the rest keep the stable one.
    assert for_pilot == {
        "version": "0.3.0",
        "channel": "pilot",
        "download_url": PILOT["download_url"],
        "sha256": PILOT["sha256"],
        "released_at": for_pilot["released_at"],
    }
    assert for_stable["version"] == "0.2.0"
    pilot_config = ok(await api_client.get(CONFIG, headers=as_device(pilot_token)))
    stable_config = ok(await api_client.get(CONFIG, headers=as_device(stable_token)))
    assert (pilot_config["latest_version"], stable_config["latest_version"]) == ("0.3.0", "0.2.0")

    ok(
        await api_client.patch(
            f"{RELEASES}/{pilot['id']}", json={"channel": "stable"}, headers=admin
        )
    )

    # Promotion is what hands the build to the rest.
    after = ok(await api_client.get(CONFIG, headers=as_device(stable_token)))
    assert after["latest_version"] == "0.3.0"
    assert await audit_records(session, "device") == [
        ("update", tester.id, {"update_channel": {"old": "stable", "new": "pilot"}})
    ]


async def test_a_withdrawn_release_and_an_empty_channel_leave_the_agent_alone(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await school_with_settings(session)
    _, token = await device_on(session, school, device_uid="PC-1")

    empty = problem(await api_client.get(LATEST, headers=as_device(token)), 404, "not_found")
    assert ok(await api_client.get(CONFIG, headers=as_device(token)))["latest_version"] is None
    session.add(
        AgentRelease(
            version="0.2.0",
            channel="stable",
            download_url=STABLE["download_url"],
            sha256=STABLE["sha256"],
            is_active=False,
        )
    )
    await session.flush()
    withdrawn = await api_client.get(LATEST, headers=as_device(token))

    assert empty["detail"] == "Для канала этого устройства нет опубликованного релиза"
    # A withdrawn release is handed out to nobody: the agent keeps the version it runs.
    problem(withdrawn, 404, "not_found")
    assert ok(await api_client.get(CONFIG, headers=as_device(token)))["latest_version"] is None


@pytest.mark.parametrize("role", ["school", "district", "provider", "oblast", "admin"])
async def test_only_the_administrator_manages_releases(
    session: AsyncSession, api_client: AsyncClient, role: str
) -> None:
    school = await create_school(session)
    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id.desc()).limit(1))
    scope = {
        "school": {"school_id": school.id},
        "district": {"region_id": school.region_id},
        "provider": {"provider_id": provider_id},
    }.get(role, {})
    user = bearer(await create_user(session, role, **scope))
    release = AgentRelease(
        version="0.2.0",
        channel="stable",
        download_url=STABLE["download_url"],
        sha256=STABLE["sha256"],
    )
    session.add(release)
    await session.flush()

    responses = [
        await api_client.get(RELEASES, headers=user),
        await api_client.post(RELEASES, json=PILOT, headers=user),
        await api_client.patch(f"{RELEASES}/{release.id}", json={"channel": "pilot"}, headers=user),
    ]

    if role == "admin":
        assert [response.status_code for response in responses] == [200, 201, 200]
        return
    for response in responses:
        problem(response, 403, "forbidden")
    # Nothing was published or moved: releases are technical administration (ТЗ п. 16).
    published = await session.scalars(select(AgentRelease.channel).order_by(AgentRelease.id))
    assert list(published) == ["stable"]
