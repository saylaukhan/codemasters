"""Panel user of a request and ``require(permission)`` (ADR-008, ADR-009).

``current_user`` turns ``Authorization: Bearer <access JWT>`` into the user and his scope; the
row is read on every request, so blocking and logout act at once, not when the 15 minutes of
the token run out. ``require`` checks the permission of the role and then limits the session of
the request to the user's scope through RLS (``app/auth/rls.py``).
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import PERMISSIONS, ROLE_PERMISSIONS
from app.auth.rls import apply_scope, clear_scope, scope_value
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import user_token
from app.core.errors import ApiError
from app.core.security import decode_jwt
from app.models import User, UserScope
from app.schemas.statuses import UserRole


@dataclass(frozen=True)
class AuthUser:
    """User behind the access token, with the scope ids of his role (ADR-008)."""

    id: int
    email: str
    full_name: str
    role: UserRole
    region_id: int | None
    provider_id: int | None
    school_id: int | None

    @property
    def permissions(self) -> frozenset[str]:
        return ROLE_PERMISSIONS[self.role]

    @property
    def scope(self) -> str:
        return scope_value(
            self.role,
            region_id=self.region_id,
            provider_id=self.provider_id,
            school_id=self.school_id,
        )


def unauthorized_user() -> ApiError:
    return ApiError(401, "unauthorized", "Требуется вход в панель", {"WWW-Authenticate": "Bearer"})


def account_blocked() -> ApiError:
    return ApiError(403, "account_blocked", "Учётная запись заблокирована администратором")


async def load_user(session: AsyncSession, user: User) -> AuthUser:
    """User with the scope ids of ``user_scopes``."""
    scope = await session.scalar(select(UserScope).where(UserScope.user_id == user.id))
    return AuthUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=cast(UserRole, user.role),
        region_id=scope.region_id if scope else None,
        provider_id=scope.provider_id if scope else None,
        school_id=scope.school_id if scope else None,
    )


async def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(user_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthUser:
    """User of ``Authorization: Bearer``; 401 without a valid token, 403 when blocked."""
    if credentials is None:
        raise unauthorized_user()
    decoded = decode_jwt(
        credentials.credentials,
        typ="access",
        now=datetime.now(UTC),
        key=get_settings().secret_key,
    )
    if decoded is None:
        raise unauthorized_user()
    user_id, version = decoded
    user = await session.get(User, user_id)
    if user is None or user.token_version != version:
        raise unauthorized_user()
    if not user.is_active:
        raise account_blocked()
    auth_user = await load_user(session, user)
    # The audit middleware writes the action under this user (app/auth/audit.py).
    request.state.user = auth_user
    return auth_user


def require(permission: str) -> Callable[..., AsyncIterator[AuthUser]]:
    """Dependency of a panel endpoint: 403 unless the role has ``permission``; the session of
    the request then sees only the rows of the user's scope (RLS)."""
    if permission not in PERMISSIONS:
        raise ValueError(f"неизвестное право {permission!r}: см. app/auth/permissions.py")

    async def check_permission(
        user: Annotated[AuthUser, Depends(current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> AsyncIterator[AuthUser]:
        if permission not in user.permissions:
            raise ApiError(403, "forbidden", f"У роли нет права {permission}")
        await apply_scope(session, user.scope)
        try:
            yield user
        finally:
            await clear_scope(session)

    return check_permission
