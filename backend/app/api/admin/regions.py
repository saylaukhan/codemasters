"""Region reference of the admin panel (plan.md §10 «Админка», ТЗ п. 20): districts and cities.

There is no DELETE: schools refer to regions. Boundaries are loaded from the VKO GeoJSON by
T-04; here they may be replaced or removed. Every change goes to the audit log (T-34).
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
    RegionCreate,
    RegionDetail,
    RegionListItemPage,
    RegionUpdate,
)
from app.services import references

router = APIRouter(
    prefix="/regions", tags=["admin"], dependencies=[Depends(require("references:manage"))]
)

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
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegionListItemPage:
    return await references.region_list(session, params, q)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить район или город",
    responses={409: REGION_CODE_TAKEN},
)
async def create_region(
    body: RegionCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> RegionDetail:
    return await references.create_region(session, body)


@router.patch(
    "/{region_id}",
    summary="Изменить район или город",
    description="Смена code не меняет School ID уже созданных школ.",
    responses={
        404: {"model": Problem, "description": "Район или город не найден"},
        409: REGION_CODE_TAKEN,
    },
)
async def update_region(
    region_id: int,
    body: RegionUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegionDetail:
    region, changes = await references.update_region(session, region_id, body)
    describe_action(request, changes=changes or None)
    return region
