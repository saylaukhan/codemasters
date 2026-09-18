"""T-39: the audit log in the admin panel — who, when, what; filters; the Администратор only.

Sign-ins (successful or not), changes of references and settings and rejected agent requests
are listed newest first (ТЗ п. 12, п. 16, п. 20); the other roles get 403 (ADR-008).
"""

from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Provider
from tests.factories import (
    PASSWORD,
    bearer,
    create_school,
    create_user,
    primary_point,
    register_device,
)

AUDIT_LOG = "/api/admin/audit-log"


def ok(response: Response) -> Any:
    assert response.status_code == 200, response.text
    return response.json()


def actions(page: dict[str, Any]) -> list[tuple[str, str | None]]:
    return [(item["action"], item["user_email"]) for item in page["items"]]


async def test_sign_ins_changes_and_transfer_errors_are_listed_newest_first(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = await create_user(session, "admin")
    as_admin = bearer(admin)
    school = await create_school(session)
    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id.desc()).limit(1))
    _, token = await register_device(session, await primary_point(session, school))

    for password in (PASSWORD, "wrong-password"):
        await api_client.post(
            "/api/auth/login", json={"email": "admin@example.kz", "password": password}
        )
    renamed = await api_client.patch(
        f"/api/admin/providers/{provider_id}", json={"name": "Провайдер Т-39"}, headers=as_admin
    )
    assert renamed.status_code == 200, renamed.text
    await api_client.post(
        "/api/outages", json={"started_at": "вчера"}, headers={"Authorization": f"Device {token}"}
    )

    page = ok(await api_client.get(AUDIT_LOG, headers=as_admin))

    assert page["total"] == 4
    assert [
        (item["action"], item["entity_type"], item["user_email"], item["error_type"])
        for item in page["items"]
    ] == [
        ("transfer_error", "device", None, "validation_error"),
        ("update", "provider", "admin@example.kz", None),
        ("login_failure", "user", "admin@example.kz", "invalid_credentials"),
        ("login_success", "user", "admin@example.kz", None),
    ]
    change = page["items"][1]
    assert change["entity_id"] == provider_id
    assert change["changes"]["name"]["new"] == "Провайдер Т-39"
    assert change["user_id"] == admin.id
    assert change["created_at"]


async def add_record(
    session: AsyncSession, created_at: datetime, action: str, **fields: Any
) -> AuditLog:
    row = AuditLog(
        created_at=created_at,
        action=action,
        entity_type=fields.pop("entity_type", "user"),
        **fields,
    )
    session.add(row)
    await session.flush()
    return row


async def test_filters_by_user_action_entity_period_and_search(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = await create_user(session, "admin")
    oblast = await create_user(session, "oblast")
    as_admin = bearer(admin)
    day = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
    await add_record(
        session,
        day,
        "login_success",
        user_id=oblast.id,
        user_email=oblast.email,
        ip=ip_address("10.0.0.7"),
    )
    await add_record(
        session,
        day + timedelta(days=1),
        "update",
        entity_type="setting",
        user_id=admin.id,
        user_email=admin.email,
        changes={"measure_server_url": {"old": "a", "new": "b"}},
    )
    await add_record(
        session, day + timedelta(days=2), "login_failure", user_email="nobody@example.kz"
    )

    by_user = ok(await api_client.get(AUDIT_LOG, params={"user_id": oblast.id}, headers=as_admin))
    assert actions(by_user) == [("login_success", "oblast@example.kz")]

    by_action = ok(
        await api_client.get(
            AUDIT_LOG,
            params=[("action", "login_success"), ("action", "login_failure")],
            headers=as_admin,
        )
    )
    assert actions(by_action) == [
        ("login_failure", "nobody@example.kz"),
        ("login_success", "oblast@example.kz"),
    ]

    by_entity = ok(
        await api_client.get(AUDIT_LOG, params={"entity_type": "setting"}, headers=as_admin)
    )
    assert by_entity["items"][0]["changes"] == {"measure_server_url": {"old": "a", "new": "b"}}

    period = {
        "period_from": (day + timedelta(days=1)).isoformat(),
        "period_to": (day + timedelta(days=2)).isoformat(),
    }
    in_period = ok(await api_client.get(AUDIT_LOG, params=period, headers=as_admin))
    assert actions(in_period) == [("update", "admin@example.kz")]

    by_email = ok(await api_client.get(AUDIT_LOG, params={"q": "NOBODY@"}, headers=as_admin))
    assert actions(by_email) == [("login_failure", "nobody@example.kz")]
    by_ip = ok(await api_client.get(AUDIT_LOG, params={"q": "10.0.0.7"}, headers=as_admin))
    assert actions(by_ip) == [("login_success", "oblast@example.kz")]
    assert by_ip["items"][0]["ip"] == "10.0.0.7"

    paged = ok(
        await api_client.get(AUDIT_LOG, params={"page_size": 2, "page": 2}, headers=as_admin)
    )
    assert (paged["total"], len(paged["items"])) == (3, 1)


@pytest.mark.parametrize("role", ["school", "district", "oblast", "provider"])
async def test_only_the_administrator_reads_the_log(
    session: AsyncSession, api_client: AsyncClient, role: str
) -> None:
    school = await create_school(session)
    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id.desc()).limit(1))
    scope = {
        "school": {"school_id": school.id},
        "district": {"region_id": school.region_id},
        "provider": {"provider_id": provider_id},
    }.get(role, {})
    user = await create_user(session, role, **scope)
    await add_record(session, datetime.now(UTC), "login_success", user_id=user.id)

    response = await api_client.get(AUDIT_LOG, headers=bearer(user))

    assert response.status_code == 403, response.text
    assert response.json()["type"] == "forbidden"
