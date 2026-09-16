"""Region reference of the admin panel (plan.md §10 «Админка», ТЗ п. 20): districts and cities.

Contract stubs: every endpoint answers 501 until T-34. There is no DELETE: schools refer to
regions. Boundaries are loaded from the VKO GeoJSON by T-04; editing them here is optional.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Security, status

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.references import (
    RegionCreate,
    RegionDetail,
    RegionListItemPage,
    RegionUpdate,
)

router = APIRouter(prefix="/regions", tags=["admin"], dependencies=[Security(user_token)])

REGION_CODE_TAKEN: dict[str, Any] = {
    "model": Problem,
    "description": "Район или город с таким кодом уже есть (type region_code_taken)",
}


@router.get(
    "",
    summary="Справочник районов и городов ВКО",
    description="Сортировка по названию. Границы в списке нет — только признак has_boundary.",
)
async def list_regions(
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[
        str | None, Query(min_length=1, max_length=255, description="Название или код")
    ] = None,
) -> RegionListItemPage:
    raise not_implemented("T-34")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить район или город",
    responses={409: REGION_CODE_TAKEN},
)
async def create_region(body: RegionCreate) -> RegionDetail:
    raise not_implemented("T-34")


@router.patch(
    "/{region_id}",
    summary="Изменить район или город",
    description="Смена code не меняет School ID уже созданных школ.",
    responses={
        404: {"model": Problem, "description": "Район или город не найден"},
        409: REGION_CODE_TAKEN,
    },
)
async def update_region(region_id: int, body: RegionUpdate) -> RegionDetail:
    raise not_implemented("T-34")
