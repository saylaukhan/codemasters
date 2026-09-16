"""User administration (plan.md §10 «Админка»): list, create, change, block (ТЗ п. 16, п. 20).

Contract stubs: every endpoint answers 501 until T-38. Only the Администратор manages users
(ADR-008). There is no DELETE: a user is blocked with ``is_active = false`` and his audit log
stays (ТЗ п. 16).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Security, status

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.statuses import UserRole
from app.schemas.users import UserCreate, UserDetail, UserDetailPage, UserUpdate

router = APIRouter(prefix="/users", tags=["admin"], dependencies=[Security(user_token)])

USER_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Пользователь не найден"}

EMAIL_TAKEN: dict[str, Any] = {
    "model": Problem,
    "description": "E-mail уже занят другим пользователем (type email_taken)",
}


@router.get(
    "",
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
) -> UserDetailPage:
    raise not_implemented("T-38")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя с ролью и областью видимости",
    description="Неизвестный region_id, provider_id или school_id — 422.",
    responses={409: EMAIL_TAKEN},
)
async def create_user(body: UserCreate) -> UserDetail:
    raise not_implemented("T-38")


@router.patch(
    "/{user_id}",
    summary="Изменить пользователя, заблокировать или сбросить пароль",
    description=(
        "role передаётся вместе с областью видимости и заменяет её целиком. "
        "Неизвестный region_id, provider_id или school_id — 422."
    ),
    responses={404: USER_NOT_FOUND, 409: EMAIL_TAKEN},
)
async def update_user(user_id: int, body: UserUpdate) -> UserDetail:
    raise not_implemented("T-38")
