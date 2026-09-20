"""T-38: users and roles in the admin panel — create, reset the password, block without deleting.

Only the Администратор manages users (ADR-008); Область gets 403. The password is stored as an
argon2 hash only (ТЗ п. 12); a blocked user cannot sign in and his audit records stay (ТЗ п. 16).
"""

from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import AuditLog, Provider, Region, User, UserScope
from tests.factories import bearer, create_school, create_user

USERS = "/api/admin/users"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"


def ok(response: Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


def invalid_fields(response: Response) -> list[str]:
    return [error["field"] for error in problem(response, 422, "validation_error")["errors"]]


async def login(client: AsyncClient, email: str, password: str) -> Response:
    return await client.post(LOGIN, json={"email": email, "password": password})


async def user_audit(session: AsyncSession, user_id: int) -> list[tuple[Any, ...]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.user_id, AuditLog.changes)
        .where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id)
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


async def test_oblast_cannot_create_users(session: AsyncSession, api_client: AsyncClient) -> None:
    oblast = bearer(await create_user(session, "oblast"))
    body = {
        "email": "new@example.kz",
        "full_name": "Новый пользователь",
        "role": "oblast",
        "password": "Password1",
    }

    problem(await api_client.post(USERS, json=body, headers=oblast), 403, "forbidden")
    problem(await api_client.get(USERS, headers=oblast), 403, "forbidden")
    problem(await api_client.get("/api/admin/roles", headers=oblast), 403, "forbidden")

    assert await session.scalar(select(User.id).where(User.email == "new@example.kz")) is None
    assert await session.scalar(select(func.count()).select_from(AuditLog)) == 0


async def test_admin_creates_resets_password_and_blocks_without_deleting(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin_user = await create_user(session, "admin")
    admin = bearer(admin_user)
    region = await session.get(Region, (await create_school(session)).region_id)
    assert region is not None
    body = {
        "email": "Rayon.New@Example.KZ",
        "full_name": "Иванова А. К.",
        "role": "district",
        "region_id": region.id,
        "password": "Initial-pass1",
    }

    created = ok(await api_client.post(USERS, json=body, headers=admin), 201)
    user_id = created["id"]
    assert created == {
        "id": user_id,
        "email": "rayon.new@example.kz",
        "full_name": "Иванова А. К.",
        "role": "district",
        "scope": {
            "region_id": region.id,
            "region_name": region.name,
            "provider_id": None,
            "school_id": None,
        },
        "scope_name": region.name,
        "is_active": True,
        # Notifications of T-42: the channel is off for him until an administrator fills it in.
        "telegram_chat_id": None,
    }
    # The password is stored only as an argon2 hash.
    stored = await session.scalar(select(User.password_hash).where(User.id == user_id))
    assert stored is not None and stored.startswith("$argon2id$")
    assert "Initial-pass1" not in stored
    problem(
        await api_client.post(USERS, json={**body, "email": "RAYON.NEW@example.kz"}, headers=admin),
        409,
        "email_taken",
    )

    signed_in = ok(await login(api_client, "rayon.new@example.kz", "Initial-pass1"))
    old_session = {"Authorization": f"Bearer {signed_in['access_token']}"}

    # A reset replaces the password and ends the sessions opened with the old one.
    ok(
        await api_client.patch(
            f"{USERS}/{user_id}", json={"password": "Reset-pass22"}, headers=admin
        )
    )
    problem(await api_client.get(ME, headers=old_session), 401, "unauthorized")
    problem(
        await login(api_client, "rayon.new@example.kz", "Initial-pass1"), 401, "invalid_credentials"
    )
    ok(await login(api_client, "rayon.new@example.kz", "Reset-pass22"))
    stored = await session.scalar(select(User.password_hash).where(User.id == user_id))
    assert stored is not None and verify_password("Reset-pass22", stored)

    blocked = ok(
        await api_client.patch(f"{USERS}/{user_id}", json={"is_active": False}, headers=admin)
    )
    assert blocked["is_active"] is False
    problem(await login(api_client, "rayon.new@example.kz", "Reset-pass22"), 403, "account_blocked")
    listed = ok(await api_client.get(USERS, params={"is_active": "false"}, headers=admin))
    assert [item["id"] for item in listed["items"]] == [user_id]

    # Blocked, not deleted: the row and every record about the user stay.
    assert await session.get(User, user_id) is not None
    assert await user_audit(session, user_id) == [
        ("create", admin_user.id, None),
        ("login_success", user_id, None),
        ("password_reset", admin_user.id, None),
        ("login_failure", user_id, None),
        ("login_success", user_id, None),
        ("block", admin_user.id, {"is_active": {"old": True, "new": False}}),
        ("login_failure", user_id, None),
    ]

    ok(await api_client.patch(f"{USERS}/{user_id}", json={"is_active": True}, headers=admin))
    ok(await login(api_client, "rayon.new@example.kz", "Reset-pass22"))
    assert (await user_audit(session, user_id))[-2][0] == "unblock"


async def test_role_change_replaces_the_scope(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))
    school = await create_school(session)
    user = await create_user(session, "district", region_id=school.region_id)
    path = f"{USERS}/{user.id}"

    oblast = ok(await api_client.patch(path, json={"role": "oblast"}, headers=admin))
    assert oblast["role"] == "oblast"
    assert oblast["scope_name"] is None
    assert await session.scalar(select(UserScope.id).where(UserScope.user_id == user.id)) is None

    moved = ok(
        await api_client.patch(path, json={"role": "school", "school_id": school.id}, headers=admin)
    )
    assert moved["scope"]["school_id"] == school.id
    assert moved["scope_name"] == school.full_name

    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id).limit(1))
    provider = ok(
        await api_client.patch(
            path, json={"role": "provider", "provider_id": provider_id}, headers=admin
        )
    )
    assert provider["scope"] == {
        "region_id": None,
        "region_name": None,
        "provider_id": provider_id,
        "school_id": None,
    }
    listed = ok(await api_client.get(USERS, params={"provider_id": provider_id}, headers=admin))
    assert [item["id"] for item in listed["items"]] == [user.id]

    # The scope changes only together with the role, and only to an existing row.
    assert invalid_fields(
        await api_client.patch(path, json={"provider_id": provider_id}, headers=admin)
    ) == ["body"]
    assert invalid_fields(
        await api_client.patch(path, json={"role": "district", "region_id": 999999}, headers=admin)
    ) == ["region_id"]
    problem(
        await api_client.patch(f"{USERS}/999999", json={"full_name": "Х"}, headers=admin),
        404,
        "not_found",
    )


async def test_admin_cannot_lock_himself_out(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin_user = await create_user(session, "admin")
    admin = bearer(admin_user)
    path = f"{USERS}/{admin_user.id}"

    assert invalid_fields(
        await api_client.patch(path, json={"is_active": False}, headers=admin)
    ) == ["is_active"]
    assert invalid_fields(await api_client.patch(path, json={"role": "oblast"}, headers=admin)) == [
        "role"
    ]
    renamed = ok(
        await api_client.patch(path, json={"full_name": "Главный администратор"}, headers=admin)
    )
    assert renamed["full_name"] == "Главный администратор"


async def test_roles_list_the_permission_matrix(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))

    roles = ok(await api_client.get("/api/admin/roles", headers=admin))

    assert [role["code"] for role in roles["items"]] == [
        "school",
        "district",
        "oblast",
        "provider",
        "admin",
    ]
    by_code = {role["code"]: set(role["permissions"]) for role in roles["items"]}
    assert "users:manage" in by_code["admin"]
    assert "users:manage" not in by_code["oblast"]
