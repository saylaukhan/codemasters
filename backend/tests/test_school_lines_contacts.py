"""T-35: lines with contracts, monitoring points and contacts of a school in the admin panel.

A school has a main and a reserve line with their own contract values (ТЗ п. 10, п. 14); a
point is bound to a line of the same school; the contact card keeps the date of its last change
(ТЗ п. 15), and its phone is shown only to roles with the right. Every change is audited.
"""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Line, Provider, SchoolContact
from tests.factories import bearer, create_school, create_settings, create_user, primary_point

PHONE = "+7 700 000 00 00"


def ok(response: Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


async def audit_records(session: AsyncSession, entity_type: str) -> list[tuple[Any, ...]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == entity_type)
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


async def test_a_school_gets_a_reserve_line_and_a_point_bound_to_it(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    other_school = await create_school(session, school_code="VKO-UK-002")
    main = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    old_point = await primary_point(session, school)
    reserve_provider = Provider(name="Резервный провайдер")
    session.add(reserve_provider)
    await session.flush()
    oblast = bearer(await create_user(session, "oblast"))
    lines = f"/api/schools/{school.id}/lines"

    reserve = ok(
        await api_client.post(
            lines,
            json={
                "provider_id": reserve_provider.id,
                "status": "reserve",
                "line_identifier": "ACC-42",
                "contract_down_mbps": 20,
                "contract_up_mbps": 10,
                "contract_number": "Д-17/2026",
                "contract_date": "2026-01-15",
                "ip_ranges": ["203.0.113.0/24"],
            },
            headers=oblast,
        ),
        201,
    )
    assert reserve["provider_name"] == "Резервный провайдер"
    assert reserve["status"] == "reserve"
    assert (reserve["contract_down_mbps"], reserve["contract_up_mbps"]) == (20, 10)
    assert (reserve["contract_number"], reserve["contract_date"]) == ("Д-17/2026", "2026-01-15")
    assert reserve["ip_ranges"] == ["203.0.113.0/24"]

    # One main line per school; unknown references are a 422 on their field.
    problem(
        await api_client.post(
            lines, json={"provider_id": reserve_provider.id, "status": "main"}, headers=oblast
        ),
        409,
        "main_line_exists",
    )
    unknown = problem(
        await api_client.post(
            lines, json={"provider_id": 10**9, "status": "reserve"}, headers=oblast
        ),
        422,
        "validation_error",
    )
    assert [error["field"] for error in unknown["errors"]] == ["provider_id"]

    ok(
        await api_client.patch(
            f"{lines}/{main.id}",
            json={"contract_down_mbps": 100, "contract_date": "2025-09-01"},
            headers=oblast,
        )
    )
    listed = ok(await api_client.get(lines, headers=oblast))["items"]
    assert [(line["status"], line["contract_down_mbps"]) for line in listed] == [
        ("main", 100),
        ("reserve", 20),
    ]

    points = f"/api/schools/{school.id}/points"
    point = ok(
        await api_client.post(
            points,
            json={
                "line_id": reserve["id"],
                "name": "Кабинет 214",
                "room": "214",
                "is_primary": True,
            },
            headers=oblast,
        ),
        201,
    )
    assert (point["line_id"], point["line_status"], point["is_primary"]) == (
        reserve["id"],
        "reserve",
        True,
    )
    # The primary mark moved from the old point to the new one.
    assert [
        (p["id"], p["is_primary"])
        for p in ok(await api_client.get(points, headers=oblast))["items"]
    ] == [
        (point["id"], True),
        (old_point.id, False),
    ]

    other_line = await session.scalar(select(Line.id).where(Line.school_id == other_school.id))
    foreign = problem(
        await api_client.patch(
            f"{points}/{point['id']}", json={"line_id": other_line}, headers=oblast
        ),
        422,
        "validation_error",
    )
    assert [error["field"] for error in foreign["errors"]] == ["line_id"]
    moved = ok(
        await api_client.patch(f"{points}/{point['id']}", json={"line_id": main.id}, headers=oblast)
    )
    assert (moved["line_id"], moved["line_status"]) == (main.id, "main")

    assert await audit_records(session, "line") == [
        ("create", reserve["id"], None),
        (
            "update",
            main.id,
            {
                "contract_down_mbps": {"old": None, "new": 100.0},
                "contract_date": {"old": None, "new": "2025-09-01"},
            },
        ),
    ]
    assert await audit_records(session, "monitoring_point") == [
        ("create", point["id"], None),
        ("update", point["id"], {"line_id": {"old": reserve["id"], "new": main.id}}),
    ]


async def test_a_contact_is_edited_and_its_phone_is_shown_by_the_rights(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    provider_id = await session.scalar(select(Line.provider_id).where(Line.school_id == school.id))
    oblast = bearer(await create_user(session, "oblast"))
    district = bearer(await create_user(session, "district", region_id=school.region_id))
    provider = bearer(await create_user(session, "provider", provider_id=provider_id))
    contacts = f"/api/schools/{school.id}/contacts"

    created = ok(
        await api_client.post(
            contacts,
            json={"full_name": "Иванова А. Б.", "position": "Учитель информатики", "phone": PHONE},
            headers=oblast,
        ),
        201,
    )
    assert created["phone"] == PHONE

    # The date of the last change is set by the database, never by the panel.
    long_ago = datetime(2025, 1, 1, tzinfo=UTC)
    await session.execute(
        update(SchoolContact).where(SchoolContact.id == created["id"]).values(updated_at=long_ago)
    )
    edited = ok(
        await api_client.patch(
            f"{contacts}/{created['id']}",
            json={"position": "Заместитель директора", "phone": "+7 701 111 11 11"},
            headers=oblast,
        )
    )
    assert edited["position"] == "Заместитель директора"
    assert datetime.fromisoformat(edited["updated_at"]) > long_ago

    seen_by_district = ok(await api_client.get(contacts, headers=district))["items"]
    seen_by_provider = ok(await api_client.get(contacts, headers=provider))["items"]
    assert [c["phone"] for c in seen_by_district] == ["+7 701 111 11 11"]
    assert [c["phone"] for c in seen_by_provider] == [None]

    # Personal values stay out of the log that is never cleaned: only the fact of the change.
    assert await audit_records(session, "school_contact") == [
        ("create", created["id"], None),
        (
            "update",
            created["id"],
            {
                "position": {"old": "Учитель информатики", "new": "Заместитель директора"},
                "phone": {"old": "***", "new": "***"},
            },
        ),
    ]


async def test_district_cannot_change_lines_points_or_contacts(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    line_id = await session.scalar(select(Line.id).where(Line.school_id == school.id))
    district = bearer(await create_user(session, "district", region_id=school.region_id))
    base = f"/api/schools/{school.id}"

    for path, body in (
        (f"{base}/lines", {"provider_id": 1, "status": "reserve"}),
        (f"{base}/points", {"line_id": line_id, "name": "Точка"}),
        (f"{base}/contacts", {"full_name": "Петров П. П."}),
    ):
        problem(await api_client.post(path, json=body, headers=district), 403, "forbidden")
    # Viewing is theirs: the points of their school are listed.
    assert ok(await api_client.get(f"{base}/points", headers=district))["total"] == 1
    assert await audit_records(session, "line") == []
