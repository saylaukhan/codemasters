"""T-25: the school card — state, computers, lines, contacts and the phone by the rights.

The card has no period: it answers at the moment of the request, so the school here is measured
relative to now — a computer heard a minute ago and three measurements of the last hours.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, Measurement, Provider, School, SchoolContact
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

PHONE = "+7 700 000 00 00"


async def measured_school(session: AsyncSession, code: str) -> tuple[School, Line]:
    """School with a main line of 50 Mbit/s by contract, a reserve line and one contact; its
    computer was heard a minute ago and measured 90, 10 and 80 Mbit/s over the last hours."""
    school = await create_school(session, school_code=code)
    device, _ = await register_device(
        session, await primary_point(session, school), device_uid=code
    )
    now = datetime.now(UTC)
    device.last_seen_at = now - timedelta(minutes=1)
    main = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    main.contract_down_mbps = 50
    reserve_provider = Provider(name=f"Резерв {code}")
    session.add(reserve_provider)
    await session.flush()
    session.add_all(
        [
            Line(school_id=school.id, provider_id=reserve_provider.id, status="reserve"),
            SchoolContact(school_id=school.id, full_name="Иванова А. Б.", phone=PHONE),
        ]
    )
    for hours, status, download in [
        (1, "normal", 90.0),
        (2, "critical", 10.0),
        (3, "normal", 80.0),
    ]:
        session.add(
            Measurement(
                measurement_uuid=uuid.uuid4(),
                measured_at=now - timedelta(hours=hours),
                device_id=device.id,
                line_id=main.id,
                connection_status="online",
                iface_type="ethernet",
                download_mbps=download,
                upload_mbps=download / 2,
                ping_ms=20.0,
                quality_status=status,
                thresholds_snapshot={
                    "download_min_mbps": 20.0,
                    "upload_min_mbps": 10.0,
                    "ping_max_ms": 100.0,
                    "jitter_max_ms": 30.0,
                    "packet_loss_max_pct": 2.0,
                },
            )
        )
    await session.flush()
    return school, main


async def get(client: AsyncClient, path: str, headers: dict[str, str]) -> Any:
    response = await client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_card_shows_the_state_the_computers_and_the_lines(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, main = await measured_school(session, "VKO-A-001")
    oblast = bearer(await create_user(session, "oblast"))

    card = await get(api_client, f"/api/schools/{school.id}", oblast)
    devices = await get(api_client, f"/api/schools/{school.id}/devices", oblast)
    lines = await get(api_client, f"/api/schools/{school.id}/lines", oblast)

    # Two of the last three are normal: the critical one in the middle does not colour it.
    assert (card["status"], card["on_reserve_line"]) == ("normal", False)
    assert card["region_name"] == "Район VKO-A-001"
    assert card["latest_measurement"]["download_mbps"] == 90.0
    assert card["latest_measurement"]["thresholds_snapshot"]["download_min_mbps"] == 20.0
    assert card["working_hours"]["start"] == "08:00:00"
    [device] = devices["items"]
    assert (device["room"], device["line_status"], device["current_status"]) == (
        "Серверная",
        "main",
        "normal",
    )
    assert device["latest_measurement"]["download_mbps"] == 90.0
    assert [line["status"] for line in lines["items"]] == ["main", "reserve"]
    assert lines["items"][0]["id"] == main.id
    assert (lines["items"][0]["contract_down_mbps"], lines["items"][0]["quality_status"]) == (
        50.0,
        "normal",
    )
    assert lines["items"][1]["quality_status"] is None


async def test_the_phone_is_hidden_from_a_role_without_the_right(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, main = await measured_school(session, "VKO-A-001")
    district = bearer(await create_user(session, "district", region_id=school.region_id))
    provider = bearer(await create_user(session, "provider", provider_id=main.provider_id))

    seen_by_district = await get(api_client, f"/api/schools/{school.id}/contacts", district)
    seen_by_provider = await get(api_client, f"/api/schools/{school.id}/contacts", provider)

    assert [(c["full_name"], c["phone"]) for c in seen_by_district["items"]] == [
        ("Иванова А. Б.", PHONE)
    ]
    assert [(c["full_name"], c["phone"]) for c in seen_by_provider["items"]] == [
        ("Иванова А. Б.", None)
    ]


async def test_a_school_outside_the_scope_is_not_found(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school_a, _ = await measured_school(session, "VKO-A-001")
    school_b, _ = await measured_school(session, "VKO-B-001")
    district_a = bearer(await create_user(session, "district", region_id=school_a.region_id))

    for path in ("", "/devices", "/lines", "/contacts"):
        response = await api_client.get(f"/api/schools/{school_b.id}{path}", headers=district_a)
        assert response.status_code == 404, (path, response.text)
        assert response.json()["type"] == "not_found"
