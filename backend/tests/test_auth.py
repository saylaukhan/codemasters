"""T-20: sign-in of the panel, tokens, blocking and ``require(permission)`` (ТЗ п. 12, п. 16)."""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import PERMISSIONS, ROLE_PERMISSIONS
from app.core.errors import PROBLEM_MEDIA_TYPE
from app.models import AuditLog, Provider, Region, User
from app.seed import DEV_PASSWORD, DEV_USERS, seed, seed_users
from tests.factories import PASSWORD, bearer, create_school, create_user

LOGIN = "/api/auth/login"
REFRESH = "/api/auth/refresh"
LOGOUT = "/api/auth/logout"
ME = "/api/auth/me"


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> Response:
    return await client.post(LOGIN, json={"email": email, "password": password})


async def audit_rows(session: AsyncSession) -> list[tuple[str, int | None, str | None, str | None]]:
    rows = await session.execute(
        select(
            AuditLog.action, AuditLog.user_id, AuditLog.user_email, AuditLog.error_type
        ).order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows.tuples()]


async def test_login_issues_tokens_and_me_shows_role_scope_and_permissions(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    user = await create_user(session, "district", region_id=school.region_id)

    response = await login(api_client, "  District@Example.KZ ")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_in_s"] == 900
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("refresh_token=")
    assert "HttpOnly" in cookie and "Path=/api/auth" in cookie and "SameSite=strict" in cookie
    me = await api_client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200, me.text
    region_name = await session.scalar(select(Region.name).where(Region.id == school.region_id))
    assert me.json() == {
        "id": user.id,
        "email": "district@example.kz",
        "full_name": user.full_name,
        "role": "district",
        "scope": {
            "region_id": school.region_id,
            "region_name": region_name,
            "provider_id": None,
            "school_id": None,
        },
        "permissions": sorted(ROLE_PERMISSIONS["district"]),
    }
    await session.refresh(user)
    assert user.last_login_at is not None
    assert await audit_rows(session) == [("login_success", user.id, "district@example.kz", None)]


async def test_wrong_password_and_unknown_email_are_refused_and_logged(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    user = await create_user(session, "oblast")

    problem(await login(api_client, "oblast@example.kz", "Password2"), 401, "invalid_credentials")
    problem(await login(api_client, "nobody@example.kz"), 401, "invalid_credentials")

    assert await audit_rows(session) == [
        ("login_failure", user.id, "oblast@example.kz", "invalid_credentials"),
        ("login_failure", None, "nobody@example.kz", "invalid_credentials"),
    ]
    ip = await session.scalar(select(AuditLog.ip).limit(1))
    assert ip is not None


async def test_blocked_user_is_locked_out_and_his_history_stays(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    user = await create_user(session, "admin")
    signed_in = await login(api_client, "admin@example.kz")
    access = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}

    user.is_active = False
    await session.flush()

    problem(await api_client.get(ME, headers=access), 403, "account_blocked")
    problem(await api_client.post(REFRESH), 403, "account_blocked")
    problem(await login(api_client, "admin@example.kz"), 403, "account_blocked")
    # A wrong password does not tell a stranger that the account exists and is blocked.
    problem(await login(api_client, "admin@example.kz", "wrong"), 401, "invalid_credentials")
    assert await audit_rows(session) == [
        ("login_success", user.id, "admin@example.kz", None),
        ("login_failure", user.id, "admin@example.kz", "account_blocked"),
        ("login_failure", user.id, "admin@example.kz", "invalid_credentials"),
    ]


async def test_refresh_rotates_the_cookie_and_logout_revokes_every_token(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_user(session, "oblast")
    signed_in = await login(api_client, "oblast@example.kz")
    access = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}

    refreshed = await api_client.post(REFRESH)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["access_token"]
    assert refreshed.headers["set-cookie"].startswith("refresh_token=")
    stolen_refresh = api_client.cookies["refresh_token"]

    logged_out = await api_client.post(LOGOUT)

    assert logged_out.status_code == 204
    assert 'refresh_token=""' in logged_out.headers["set-cookie"]
    problem(await api_client.get(ME, headers=access), 401, "unauthorized")
    replayed = await api_client.post(REFRESH, headers={"Cookie": f"refresh_token={stolen_refresh}"})
    problem(replayed, 401, "invalid_refresh_token")


async def test_tokens_of_the_wrong_kind_or_forged_are_unauthorized(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_user(session, "oblast")
    await login(api_client, "oblast@example.kz")
    refresh_token = api_client.cookies["refresh_token"]

    # A refresh token is not an access token.
    as_access = {"Authorization": f"Bearer {refresh_token}"}
    body = problem(await api_client.get(ME, headers=as_access), 401, "unauthorized")
    assert body["detail"]
    header, payload, _ = refresh_token.split(".")
    forged = {"Authorization": f"Bearer {header}.{payload}.AAAA"}
    problem(await api_client.get(ME, headers=forged), 401, "unauthorized")
    problem(await api_client.get(ME), 401, "unauthorized")


ADMIN_ONLY = ("POST", "/api/admin/users")
MONITORING_SETUP = ("POST", "/api/admin/thresholds")
VIEW = ("GET", "/api/appeals/1/pdf")
INCIDENT_STATUS = ("POST", "/api/incidents/1/status")
SCHOOL_CHANGE = ("POST", "/api/schools")

# Who passes require(...) of each endpoint (plan.md §9); the others get 403.
ALLOWED = {
    ADMIN_ONLY: {"admin"},
    MONITORING_SETUP: {"oblast", "admin"},
    VIEW: {"school", "district", "oblast", "provider", "admin"},
    INCIDENT_STATUS: {"district", "oblast", "provider", "admin"},
    SCHOOL_CHANGE: {"oblast", "admin"},
}


@pytest.mark.parametrize("role", ["school", "district", "oblast", "provider", "admin"])
async def test_require_lets_only_the_roles_of_the_permission_through(
    session: AsyncSession, api_client: AsyncClient, role: str
) -> None:
    school = await create_school(session)
    scope = {
        "school": {"school_id": school.id},
        "district": {"region_id": school.region_id},
        "provider": {"provider_id": await first_provider_id(session)},
    }.get(role, {})
    user = await create_user(session, role, **scope)

    for (method, path), roles in ALLOWED.items():
        response = await api_client.request(
            method, path, headers=bearer(user), json={} if method != "GET" else None
        )
        if role in roles:
            # Through the permission check: the endpoint itself is still a stub or validates.
            assert response.status_code in (422, 501), (method, path, response.text)
        else:
            problem(response, 403, "forbidden")


async def first_provider_id(session: AsyncSession) -> int:
    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id).limit(1))
    assert provider_id is not None
    return provider_id


async def test_stub_answers_not_implemented_after_the_permission_check(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    user = await create_user(session, "oblast")

    body = problem(
        await api_client.get("/api/appeals/1/pdf", headers=bearer(user)),
        501,
        "not_implemented",
    )

    assert "T-48" in body["detail"]


def test_every_role_has_permissions_and_administration_is_the_admins() -> None:
    assert set(ROLE_PERMISSIONS) == {"school", "district", "oblast", "provider", "admin"}
    assert ROLE_PERMISSIONS["admin"] == PERMISSIONS
    for role in ("school", "district", "oblast", "provider"):
        assert not ROLE_PERMISSIONS[role] & {"users:manage", "devices:manage", "audit:read"}
    # Школа and Провайдер only view and react; the setup of the monitoring is not theirs.
    for role in ("school", "district", "provider"):
        assert "thresholds:manage" not in ROLE_PERMISSIONS[role]


async def test_dev_users_of_the_seed_sign_in_with_their_scope(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await seed(session)

    created = await seed_users(session)
    created_again = await seed_users(session)

    assert (created, created_again) == (len(DEV_USERS), 0)
    for email, (role, _) in DEV_USERS.items():
        response = await login(api_client, email, DEV_PASSWORD)
        assert response.status_code == 200, (email, response.text)
        me = await api_client.get(
            ME, headers={"Authorization": f"Bearer {response.json()['access_token']}"}
        )
        scope = me.json()["scope"]
        assert me.json()["role"] == role
        assert (scope["region_name"], scope["school_id"] is not None) == {
            "district": ("Усть-Каменогорск", False),
            "school": (None, True),
        }.get(role, (None, False))
    stored = await session.scalars(select(User.password_hash))
    assert all(value.startswith("$argon2id$") for value in stored)
