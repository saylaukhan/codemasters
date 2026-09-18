"""T-26: the device card and its measurement history — fields, pages, period and the scope."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, Measurement, School
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)


async def measured_device(session: AsyncSession, code: str) -> tuple[Device, Line, datetime]:
    """Computer heard a minute ago with measurements 1, 2 and 3 hours ago; the newest is Wi-Fi."""
    school = await create_school(session, school_code=code)
    point = await primary_point(session, school)
    device, _ = await register_device(session, point, device_uid=code)
    now = datetime.now(UTC)
    device.last_seen_at = now - timedelta(minutes=1)
    device.hostname, device.agent_version = f"PC-{code}", "1.2.0"
    line = await session.get_one(Line, point.line_id)
    for hours, iface, status in [
        (1, "wifi", "unstable"),
        (2, "ethernet", "normal"),
        (3, "ethernet", "critical"),
    ]:
        session.add(
            Measurement(
                measurement_uuid=uuid.uuid4(),
                measured_at=now - timedelta(hours=hours),
                device_id=device.id,
                line_id=line.id,
                connection_status="online",
                iface_type=iface,
                download_mbps=100.0 - hours,
                upload_mbps=50.0,
                ping_ms=20.0,
                quality_status=status,
                agent_version="1.2.0",
            )
        )
    await session.flush()
    return device, line, now


async def get(client: AsyncClient, path: str, headers: dict[str, str]) -> Any:
    response = await client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_card_shows_the_computer_and_its_history_newest_first(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    device, _, now = await measured_device(session, "VKO-A-001")
    oblast = bearer(await create_user(session, "oblast"))

    card = await get(api_client, f"/api/devices/{device.id}", oblast)
    first = await get(api_client, f"/api/devices/{device.id}/measurements?page_size=2", oblast)
    second = await get(
        api_client, f"/api/devices/{device.id}/measurements?page_size=2&page=2", oblast
    )
    since = (now - timedelta(hours=2, minutes=30)).isoformat().replace("+00:00", "Z")
    recent = await get(
        api_client, f"/api/devices/{device.id}/measurements?period_from={since}", oblast
    )

    assert (card["device_uid"], card["hostname"], card["agent_version"]) == (
        "VKO-A-001",
        "PC-VKO-A-001",
        "1.2.0",
    )
    assert (card["room"], card["school_code"], card["current_status"]) == (
        "Серверная",
        "VKO-A-001",
        "unstable",
    )
    assert card["latest_measurement"]["iface_type"] == "wifi"
    assert first["total"] == 3
    assert [m["iface_type"] for m in first["items"]] == ["wifi", "ethernet"]
    assert [m["quality_status"] for m in second["items"]] == ["critical"]
    assert [m["download_mbps"] for m in recent["items"]] == [99.0, 98.0]


async def test_a_device_outside_the_scope_is_not_found(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    device_a, line_a, _ = await measured_device(session, "VKO-A-001")
    device_b, _, _ = await measured_device(session, "VKO-B-001")
    school_a = await session.get_one(School, line_a.school_id)
    district_a = bearer(await create_user(session, "district", region_id=school_a.region_id))
    provider_a = bearer(await create_user(session, "provider", provider_id=line_a.provider_id))

    for headers in (district_a, provider_a):
        assert (
            await api_client.get(f"/api/devices/{device_a.id}", headers=headers)
        ).status_code == 200
        for path in ("", "/measurements"):
            response = await api_client.get(f"/api/devices/{device_b.id}{path}", headers=headers)
            assert response.status_code == 404, (path, response.text)
            assert response.json()["type"] == "not_found"
