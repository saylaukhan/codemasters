"""Connection type reference of the admin panel (T-34, ТЗ п. 14, п. 20): fiber, ADSL, radio.

Contract stubs: every endpoint answers 501 until T-34. There is no DELETE: lines refer to
connection types. plan.md §10 does not list this path; T-34 requires it.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.auth import require
from app.core.deps import PageParams, page_params
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.references import (
    ConnectionTypeCreate,
    ConnectionTypeDetail,
    ConnectionTypeDetailPage,
    ConnectionTypeUpdate,
)

router = APIRouter(
    prefix="/connection-types", tags=["admin"], dependencies=[Depends(require("references:manage"))]
)

CONNECTION_TYPE_CODE_TAKEN: dict[str, Any] = {
    "model": Problem,
    "description": "Тип подключения с таким кодом уже есть (type connection_type_code_taken)",
}


@router.get("", summary="Справочник типов подключения", description="Сортировка по названию.")
async def list_connection_types(
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[
        str | None, Query(min_length=1, max_length=255, description="Название или код")
    ] = None,
) -> ConnectionTypeDetailPage:
    raise not_implemented("T-34")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить тип подключения",
    responses={409: CONNECTION_TYPE_CODE_TAKEN},
)
async def create_connection_type(body: ConnectionTypeCreate) -> ConnectionTypeDetail:
    raise not_implemented("T-34")


@router.patch(
    "/{connection_type_id}",
    summary="Изменить тип подключения",
    responses={
        404: {"model": Problem, "description": "Тип подключения не найден"},
        409: CONNECTION_TYPE_CODE_TAKEN,
    },
)
async def update_connection_type(
    connection_type_id: int, body: ConnectionTypeUpdate
) -> ConnectionTypeDetail:
    raise not_implemented("T-34")
