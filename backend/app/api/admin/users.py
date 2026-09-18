"""User administration (plan.md §10 «Админка»): list, create, change, block (ТЗ п. 16, п. 20).

Only the Администратор manages users (ADR-008). There is no DELETE: a user is blocked with
``is_active = false`` and his audit log stays (ТЗ п. 16). A block, an unblock and a password
reset go to the audit log as actions of their own, never with the password (T-38).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.errors import Problem
from app.schemas.statuses import UserRole
from app.schemas.users import UserCreate, UserDetail, UserDetailPage, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["admin"])

USER_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Пользователь не найден"}

EMAIL_TAKEN: dict[str, Any] = {
    "model": Problem,
    "description": "E-mail уже занят другим пользователем (type email_taken)",
}


@router.get(
    "",
    dependencies=[Depends(require("users:manage"))],
    summary="Пользователи панели с ролью и областью видимости",
    description="По full_name. region_id, provider_id и school_id отбирают по области видимости.",
)
async def list_users(
    params: Annotated[PageParams, Depends(page_params)],
    role: Annotated[
        list[UserRole] | None, Query(description="Роли; несколько — повтором параметра")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="true — активные, false — заблокированные; не задан — все")
    ] = None,
    region_id: Annotated[int | None, Query(description="Район или город (regions)")] = None,
    provider_id: int | None = None,
    school_id: int | None = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=255, description="Часть ФИО или e-mail")
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDetailPage:
    return await users.user_list(
        session,
        params,
        roles=role,
        is_active=is_active,
        region_id=region_id,
        provider_id=provider_id,
        school_id=school_id,
        q=q,
    )


@router.post(
    "",
    dependencies=[Depends(require("users:manage"))],
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя с ролью и областью видимости",
    description="Неизвестный region_id, provider_id или school_id — 422.",
    responses={409: EMAIL_TAKEN},
)
async def create_user(
    body: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> UserDetail:
    return await users.create_user(session, body)


@router.patch(
    "/{user_id}",
    summary="Изменить пользователя, заблокировать или сбросить пароль",
    description=(
        "role передаётся вместе с областью видимости и заменяет её целиком. "
        "Неизвестный region_id, provider_id или school_id — 422. Блокировка и новый пароль "
        "завершают все сессии пользователя. Заблокировать себя или сменить себе роль нельзя — 422."
    ),
    responses={404: USER_NOT_FOUND, 409: EMAIL_TAKEN},
)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    actor: Annotated[AuthUser, Depends(require("users:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDetail:
    user, action, changes = await users.update_user(session, user_id, body, actor)
    describe_action(request, action=action, changes=changes or None)
    return user
