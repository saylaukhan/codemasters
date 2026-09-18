"""T-34: schools, districts and cities, providers and connection types in the admin panel.

Область and Администратор create and edit them (ADR-008); nothing is deleted — a school is
deactivated and keeps its history (ТЗ п. 20). Every change lands in ``audit_log``.
"""

from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Region, School
from tests.factories import bearer, create_school, create_settings, create_user

BOUNDARY = {
    "type": "MultiPolygon",
    "coordinates": [[[[82.5, 49.9], [82.7, 49.9], [82.7, 50.0], [82.5, 49.9]]]],
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


async def audit_records(session: AsyncSession, entity_type: str) -> list[tuple[Any, ...]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == entity_type)
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


async def test_district_cannot_create_school(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    district = await create_user(session, "district", region_id=school.region_id)
    body = {"school_code": "VKO-UK-777", "full_name": "Новая школа", "region_id": school.region_id}

    problem(
        await api_client.post("/api/schools", json=body, headers=bearer(district)), 403, "forbidden"
    )
    problem(
        await api_client.patch(
            f"/api/schools/{school.id}", json={"is_active": False}, headers=bearer(district)
        ),
        403,
        "forbidden",
    )
    problem(
        await api_client.post(
            "/api/admin/providers", json={"name": "Чужой"}, headers=bearer(district)
        ),
        403,
        "forbidden",
    )

    assert await session.scalar(select(School.id).where(School.school_code == "VKO-UK-777")) is None
    assert await audit_records(session, "school") == []


async def test_school_is_created_edited_and_deactivated(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    existing = await create_school(session)
    oblast = bearer(await create_user(session, "oblast"))
    body = {
        "school_code": "VKO-UK-017",
        "full_name": "Школа-лицей № 17",
        "region_id": existing.region_id,
        "address": "ул. Абая, 1",
        "location": {"lat": 49.9483, "lon": 82.6286},
    }

    created = ok(await api_client.post("/api/schools", json=body, headers=oblast), 201)
    assert created["school_code"] == "VKO-UK-017"
    assert created["address"] == "ул. Абая, 1"
    assert created["location"] == {"lat": 49.9483, "lon": 82.6286}
    assert created["is_active"] is True

    school_id = created["id"]
    updated = ok(
        await api_client.patch(
            f"/api/schools/{school_id}",
            json={"full_name": "Школа-лицей № 17 им. Абая", "location": None, "is_active": False},
            headers=oblast,
        )
    )
    assert updated["full_name"] == "Школа-лицей № 17 им. Абая"
    assert updated["location"] is None
    assert updated["is_active"] is False
    # Deactivated, not deleted: the card still opens.
    assert ok(await api_client.get(f"/api/schools/{school_id}", headers=oblast))["id"] == school_id

    assert await audit_records(session, "school") == [
        ("create", school_id, None),
        (
            "update",
            school_id,
            {
                "full_name": {"old": "Школа-лицей № 17", "new": "Школа-лицей № 17 им. Абая"},
                "is_active": {"old": True, "new": False},
                "location": {"old": {"lat": 49.9483, "lon": 82.6286}, "new": None},
            },
        ),
    ]


async def test_school_code_and_region_are_checked(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    existing = await create_school(session)
    other = await create_school(session, school_code="VKO-UK-002")
    admin = bearer(await create_user(session, "admin"))
    body = {
        "school_code": existing.school_code,
        "full_name": "Дубль",
        "region_id": existing.region_id,
    }

    problem(
        await api_client.post("/api/schools", json=body, headers=admin), 409, "school_code_taken"
    )
    problem(
        await api_client.patch(
            f"/api/schools/{other.id}", json={"school_code": existing.school_code}, headers=admin
        ),
        409,
        "school_code_taken",
    )
    unknown_region = problem(
        await api_client.post(
            "/api/schools",
            json={**body, "school_code": "VKO-UK-003", "region_id": 0},
            headers=admin,
        ),
        422,
        "validation_error",
    )
    assert [error["field"] for error in unknown_region["errors"]] == ["region_id"]
    problem(
        await api_client.patch("/api/schools/0", json={"full_name": "Нет"}, headers=admin),
        404,
        "not_found",
    )
    # Its own School ID is not «taken».
    same_code = {"school_code": other.school_code}
    ok(await api_client.patch(f"/api/schools/{other.id}", json=same_code, headers=admin))


async def test_providers_are_created_listed_and_edited(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))
    body = {"name": "ТОО «Тест Телеком»", "appeals_email": "support@example.kz"}

    created = ok(await api_client.post("/api/admin/providers", json=body, headers=oblast), 201)
    assert created == {"id": created["id"], **body}
    problem(
        await api_client.post("/api/admin/providers", json=body, headers=oblast),
        409,
        "provider_name_taken",
    )

    page = ok(await api_client.get("/api/admin/providers", params={"q": "тест"}, headers=oblast))
    assert page["items"] == [created]
    assert page["total"] == 1

    updated = ok(
        await api_client.patch(
            f"/api/admin/providers/{created['id']}", json={"appeals_email": None}, headers=oblast
        )
    )
    assert updated["appeals_email"] is None
    assert await audit_records(session, "provider") == [
        ("create", created["id"], None),
        ("update", created["id"], {"appeals_email": {"old": "support@example.kz", "new": None}}),
    ]


async def test_regions_are_created_listed_and_edited(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))
    body = {"code": "TST", "name": "Тестовый район", "boundary": BOUNDARY}

    created = ok(await api_client.post("/api/admin/regions", json=body, headers=admin), 201)
    assert created["code"] == "TST"
    assert created["boundary"] == BOUNDARY
    problem(
        await api_client.post("/api/admin/regions", json=body, headers=admin),
        409,
        "region_code_taken",
    )

    page = ok(await api_client.get("/api/admin/regions", params={"q": "TST"}, headers=admin))
    assert page["items"] == [
        {"id": created["id"], "code": "TST", "name": "Тестовый район", "has_boundary": True}
    ]

    updated = ok(
        await api_client.patch(
            f"/api/admin/regions/{created['id']}",
            json={"name": "Тестовый город", "boundary": None},
            headers=admin,
        )
    )
    assert updated["name"] == "Тестовый город"
    assert updated["boundary"] is None
    assert await session.scalar(select(Region.geom).where(Region.id == created["id"])) is None
    assert await audit_records(session, "region") == [
        ("create", created["id"], None),
        (
            "update",
            created["id"],
            {
                "name": {"old": "Тестовый район", "new": "Тестовый город"},
                "has_boundary": {"old": True, "new": False},
            },
        ),
    ]


async def test_connection_types_are_created_listed_and_edited(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))
    body = {"code": "test_radio", "name": "Тестовый радиоканал"}

    created = ok(
        await api_client.post("/api/admin/connection-types", json=body, headers=oblast), 201
    )
    assert created == {"id": created["id"], **body}
    problem(
        await api_client.post("/api/admin/connection-types", json=body, headers=oblast),
        409,
        "connection_type_code_taken",
    )
    problem(
        await api_client.post(
            "/api/admin/connection-types", json={"code": "Radio", "name": "x"}, headers=oblast
        ),
        422,
        "validation_error",
    )

    updated = ok(
        await api_client.patch(
            f"/api/admin/connection-types/{created['id']}",
            json={"name": "Радиоканал"},
            headers=oblast,
        )
    )
    assert updated == {**created, "name": "Радиоканал"}
    page = ok(
        await api_client.get("/api/admin/connection-types", params={"q": "test_"}, headers=oblast)
    )
    assert page["items"] == [updated]
    problem(
        await api_client.patch("/api/admin/connection-types/0", json={}, headers=oblast),
        404,
        "not_found",
    )
    assert await audit_records(session, "connection_type") == [
        ("create", created["id"], None),
        ("update", created["id"], {"name": {"old": "Тестовый радиоканал", "new": "Радиоканал"}}),
    ]
