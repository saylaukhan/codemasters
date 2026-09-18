"""Provider reference of the admin panel (plan.md §10 «Админка», ТЗ п. 14, п. 20).

Contract stubs: every endpoint answers 501 until T-34. There is no DELETE: lines of schools
refer to providers. References are edited by Область and Администратор (ADR-008), from T-20.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.auth import require
from app.core.deps import PageParams, page_params
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.references import (
    ProviderCreate,
    ProviderDetail,
    ProviderDetailPage,
    ProviderUpdate,
)

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
) -> ProviderDetailPage:
    raise not_implemented("T-34")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить поставщика",
    responses={409: PROVIDER_NAME_TAKEN},
)
async def create_provider(body: ProviderCreate) -> ProviderDetail:
    raise not_implemented("T-34")


@router.patch(
    "/{provider_id}",
    summary="Изменить поставщика",
    responses={
        404: {"model": Problem, "description": "Поставщик не найден"},
        409: PROVIDER_NAME_TAKEN,
    },
)
async def update_provider(provider_id: int, body: ProviderUpdate) -> ProviderDetail:
    raise not_implemented("T-34")
