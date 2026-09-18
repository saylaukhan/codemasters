"""Provider reference of the admin panel (plan.md §10 «Админка», ТЗ п. 14, п. 20).

There is no DELETE: lines of schools refer to providers. References are edited by Область and
Администратор (ADR-008); every change goes to the audit log with its changed fields (T-34).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.errors import Problem
from app.schemas.references import (
    ProviderCreate,
    ProviderDetail,
    ProviderDetailPage,
    ProviderUpdate,
)
from app.services import references

router = APIRouter(
    prefix="/providers", tags=["admin"], dependencies=[Depends(require("references:manage"))]
)

PROVIDER_NAME_TAKEN: dict[str, Any] = {
    "model": Problem,
    "description": "Поставщик с таким названием уже есть (type provider_name_taken)",
}


@router.get("", summary="Справочник поставщиков интернета", description="Сортировка по названию.")
async def list_providers(
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[
        str | None, Query(min_length=1, max_length=255, description="Часть названия")
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderDetailPage:
    return await references.provider_list(session, params, q)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить поставщика",
    responses={409: PROVIDER_NAME_TAKEN},
)
async def create_provider(
    body: ProviderCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> ProviderDetail:
    return await references.create_provider(session, body)


@router.patch(
    "/{provider_id}",
    summary="Изменить поставщика",
    responses={
        404: {"model": Problem, "description": "Поставщик не найден"},
        409: PROVIDER_NAME_TAKEN,
    },
)
async def update_provider(
    provider_id: int,
    body: ProviderUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderDetail:
    provider, changes = await references.update_provider(session, provider_id, body)
    describe_action(request, changes=changes or None)
    return provider
