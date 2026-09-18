"""Panel authentication (plan.md §10, ADR-009): login, token refresh, logout, current user.

Login answers the access JWT (15 minutes, kept in memory by the panel) and sets the refresh JWT
in the httpOnly cookie ``refresh_token``, sent back only to ``/api/auth``. Refresh rotates the
cookie; logout raises ``users.token_version``, and every token of the user issued before dies —
access tokens too, since ``current_user`` compares the version on each request. Every sign-in,
successful or not, is written to ``audit_log`` (ТЗ п. 12).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, Security, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.audit import record_login
from app.auth.deps import AuthUser, account_blocked, current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import refresh_cookie
from app.core.errors import ApiError
from app.core.security import (
    burn_password_check,
    decode_jwt,
    encode_jwt,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import Region, User
from app.schemas.auth import AccessTokenResponse, CurrentUser, LoginRequest, UserScope
from app.schemas.errors import Problem

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=14)
REFRESH_COOKIE = "refresh_token"
# The cookie goes only to the endpoints that read it.
REFRESH_COOKIE_PATH = "/api/auth"

ACCOUNT_BLOCKED: dict[str, Any] = {
    "model": Problem,
    "description": "Учётная запись заблокирована (type account_blocked)",
}


def invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Неверный e-mail или пароль")


def invalid_refresh_token() -> ApiError:
    return ApiError(401, "invalid_refresh_token", "Сессия истекла, войдите снова")


def secure_cookie() -> bool:
    # Behind Caddy the API is https; a local http://localhost panel needs a non-secure cookie.
    return get_settings().api_base_url.startswith("https://")


def issue_tokens(user: User, response: Response) -> AccessTokenResponse:
    """Access token in the body, refresh token in the cookie of ``response``."""
    now = datetime.now(UTC)
    key = get_settings().secret_key
    access = encode_jwt(
        user_id=user.id,
        version=user.token_version,
        typ="access",
        issued_at=now,
        expires_at=now + ACCESS_TOKEN_TTL,
        key=key,
    )
    refresh = encode_jwt(
        user_id=user.id,
        version=user.token_version,
        typ="refresh",
        issued_at=now,
        expires_at=now + REFRESH_TOKEN_TTL,
        key=key,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        path=REFRESH_COOKIE_PATH,
        secure=secure_cookie(),
        httponly=True,
        samesite="strict",
    )
    return AccessTokenResponse(
        access_token=access, expires_in_s=int(ACCESS_TOKEN_TTL.total_seconds())
    )


async def refresh_user(session: AsyncSession, token: str | None) -> User | None:
    """Owner of a valid refresh token whose version is still current."""
    decoded = decode_jwt(
        token or "", typ="refresh", now=datetime.now(UTC), key=get_settings().secret_key
    )
    if decoded is None:
        return None
    user_id, version = decoded
    user = await session.get(User, user_id)
    if user is None or user.token_version != version:
        return None
    return user


@router.post(
    "/login",
    summary="Вход в панель по e-mail и паролю",
    responses={
        401: {
            "model": Problem,
            "description": "Неверный e-mail или пароль (type invalid_credentials)",
        },
        403: ACCOUNT_BLOCKED,
    },
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccessTokenResponse:
    email = body.email.strip().lower()
    password = body.password.get_secret_value()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        if user is None:
            burn_password_check(password)
        record_login(
            session,
            request,
            email=email,
            user_id=user.id if user else None,
            error_type="invalid_credentials",
        )
        await session.commit()
        raise invalid_credentials()
    # The password is checked first: a blocked account is not revealed to a stranger.
    if not user.is_active:
        record_login(session, request, email=email, user_id=user.id, error_type="account_blocked")
        await session.commit()
        raise account_blocked()
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    record_login(session, request, email=email, user_id=user.id)
    await session.commit()
    return issue_tokens(user, response)


@router.post(
    "/refresh",
    summary="Новый access-токен по refresh-cookie",
    responses={
        401: {
            "model": Problem,
            "description": "Refresh-токен недействителен (type invalid_refresh_token)",
        },
        403: ACCOUNT_BLOCKED,
    },
)
async def refresh_access_token(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str | None, Security(refresh_cookie)],
) -> AccessTokenResponse:
    user = await refresh_user(session, token)
    if user is None:
        raise invalid_refresh_token()
    if not user.is_active:
        raise account_blocked()
    return issue_tokens(user, response)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход из панели",
)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str | None, Security(refresh_cookie)],
) -> None:
    user = await refresh_user(session, token)
    if user is not None:
        user.token_version += 1
        await session.commit()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=secure_cookie(),
        httponly=True,
        samesite="strict",
    )


@router.get("/me", summary="Текущий пользователь: роль, область видимости, права")
async def get_current_user(
    user: Annotated[AuthUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    region_name = (
        await session.scalar(select(Region.name).where(Region.id == user.region_id))
        if user.region_id is not None
        else None
    )
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        scope=UserScope(
            region_id=user.region_id,
            region_name=region_name,
            provider_id=user.provider_id,
            school_id=user.school_id,
        ),
        permissions=sorted(user.permissions),
    )
