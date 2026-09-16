"""Panel authentication (plan.md §10): login, token refresh, logout, current user.

Contract stubs: every endpoint answers 501 until T-20. The refresh token travels only in the
httpOnly cookie ``refresh_token`` (ADR-009); cookie attributes and rotation — T-20.
"""

from typing import Any

from fastapi import APIRouter, Security, status

from app.core.deps import refresh_cookie, user_token
from app.core.errors import not_implemented
from app.schemas.auth import AccessTokenResponse, CurrentUser, LoginRequest
from app.schemas.errors import Problem

router = APIRouter(prefix="/auth", tags=["auth"])

ACCOUNT_BLOCKED: dict[str, Any] = {
    "model": Problem,
    "description": "Учётная запись заблокирована (type account_blocked)",
}


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
async def login(body: LoginRequest) -> AccessTokenResponse:
    raise not_implemented("T-20")


@router.post(
    "/refresh",
    summary="Новый access-токен по refresh-cookie",
    dependencies=[Security(refresh_cookie)],
    responses={
        401: {
            "model": Problem,
            "description": "Refresh-токен недействителен (type invalid_refresh_token)",
        },
        403: ACCOUNT_BLOCKED,
    },
)
async def refresh_access_token() -> AccessTokenResponse:
    raise not_implemented("T-20")


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход из панели",
    dependencies=[Security(refresh_cookie)],
)
async def logout() -> None:
    raise not_implemented("T-20")


@router.get(
    "/me",
    summary="Текущий пользователь: роль, область видимости, права",
    dependencies=[Security(user_token)],
)
async def get_current_user() -> CurrentUser:
    raise not_implemented("T-20")
