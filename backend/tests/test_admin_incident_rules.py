"""T-40: incident rules in the admin panel (ТЗ п. 18, п. 20; ADR-007).

N in a row, T minutes and M normal results are not in the code: Область and Администратор
change them, the next detection applies them, and the audit log keeps what was changed.
"""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, IncidentRule, Provider
from tests.factories import bearer, create_school, create_user

RULES = "/api/admin/incident-rules"

# Defaults of the migration: name, metric, N, T, M.
DEFAULT_RULES = [
    ("Download ниже порога", "download_mbps", 3, None, 2),
    ("Upload ниже порога", "upload_mbps", 3, None, 2),
    ("Ping выше порога", "ping_ms", 3, None, 2),
    ("Jitter выше порога", "jitter_ms", 3, None, 2),
    ("Потери пакетов выше порога", "packet_loss_pct", 3, None, 2),
    ("Нет соединения", "no_connection", 3, 30, 2),
]
NEW_RULE = {
    "name": "Долгий высокий ping",
    "metric": "ping_ms",
    "duration_min": 60,
    "recovery_normal_count": 3,
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


async def audit_records(session: AsyncSession) -> list[tuple[Any, ...]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == "incident_rule")
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


async def test_default_rules_are_listed(session: AsyncSession, api_client: AsyncClient) -> None:
    oblast = bearer(await create_user(session, "oblast"))

    page = ok(await api_client.get(RULES, headers=oblast))

    assert page["total"] == len(DEFAULT_RULES)
    assert [
        (
            rule["name"],
            rule["metric"],
            rule["consecutive_violations"],
            rule["duration_min"],
            rule["recovery_normal_count"],
        )
        for rule in page["items"]
    ] == DEFAULT_RULES
    assert all(rule["is_active"] for rule in page["items"])


async def test_rule_is_created_and_changed_with_audit(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))
    download_id = ok(await api_client.get(RULES, headers=admin))["items"][0]["id"]

    created = ok(await api_client.post(RULES, json=NEW_RULE, headers=admin), 201)
    changed = ok(
        await api_client.patch(
            f"{RULES}/{download_id}", json={"consecutive_violations": 5}, headers=admin
        )
    )
    switched_off = ok(
        await api_client.patch(f"{RULES}/{created['id']}", json={"is_active": False}, headers=admin)
    )

    assert created == {
        "id": created["id"],
        "consecutive_violations": None,
        "is_active": True,
        **NEW_RULE,
    }
    assert changed["consecutive_violations"] == 5
    assert switched_off["is_active"] is False
    # A switched-off rule stays in the list: its incidents refer to it.
    listed = ok(await api_client.get(RULES, headers=admin))
    assert listed["items"][-1] == switched_off
    assert await audit_records(session) == [
        ("create", created["id"], None),
        ("update", download_id, {"consecutive_violations": {"old": 3, "new": 5}}),
        ("update", created["id"], {"is_active": {"old": True, "new": False}}),
    ]


async def test_rule_without_an_opening_condition_is_rejected(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))
    download = ok(await api_client.get(RULES, headers=oblast))["items"][0]
    path = f"{RULES}/{download['id']}"

    problem(
        await api_client.post(RULES, json=NEW_RULE | {"duration_min": None}, headers=oblast),
        422,
        "validation_error",
    )
    # T is already empty: clearing N leaves no condition, although the body alone is valid.
    problem(
        await api_client.patch(path, json={"consecutive_violations": None}, headers=oblast),
        422,
        "validation_error",
    )
    problem(
        await api_client.patch(
            path, json={"consecutive_violations": None, "duration_min": None}, headers=oblast
        ),
        422,
        "validation_error",
    )
    unchanged = ok(await api_client.get(RULES, headers=oblast))["items"][0]
    # Setting T in the same body makes clearing N valid.
    swapped = ok(
        await api_client.patch(
            path, json={"consecutive_violations": None, "duration_min": 45}, headers=oblast
        )
    )

    assert unchanged == download
    assert (swapped["consecutive_violations"], swapped["duration_min"]) == (None, 45)
    assert await audit_records(session) == [
        (
            "update",
            download["id"],
            {
                "consecutive_violations": {"old": 3, "new": None},
                "duration_min": {"old": None, "new": 45},
            },
        )
    ]


async def test_unknown_rule_is_not_found(session: AsyncSession, api_client: AsyncClient) -> None:
    oblast = bearer(await create_user(session, "oblast"))

    body = problem(
        await api_client.patch(f"{RULES}/999999", json={"is_active": False}, headers=oblast),
        404,
        "not_found",
    )

    assert body["detail"] == "Правило инцидентов не найдено"


@pytest.mark.parametrize("role", ["school", "district", "provider", "oblast", "admin"])
async def test_only_oblast_and_administrator_manage_rules(
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
    rule_id = await session.scalar(select(IncidentRule.id).order_by(IncidentRule.id).limit(1))

    responses = [
        await api_client.get(RULES, headers=user),
        await api_client.post(RULES, json=NEW_RULE, headers=user),
        await api_client.patch(f"{RULES}/{rule_id}", json={"is_active": False}, headers=user),
    ]

    if role in ("oblast", "admin"):
        assert [response.status_code for response in responses] == [200, 201, 200]
        return
    for response in responses:
        problem(response, 403, "forbidden")
    # «Роль района не может править правила» (T-40): nothing is created or switched off.
    active = await session.scalars(select(IncidentRule.is_active).order_by(IncidentRule.id))
    assert list(active) == [True] * len(DEFAULT_RULES)
