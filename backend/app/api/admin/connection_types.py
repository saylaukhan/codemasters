"""Connection type reference of the admin panel (T-34, ТЗ п. 14, п. 20): fiber, ADSL, radio.

There is no DELETE: lines refer to connection types. plan.md §10 does not list this path; T-34
requires it. Every change goes to the audit log with its changed fields.
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
    ConnectionTypeCreate,
    ConnectionTypeDetail,
    ConnectionTypeDetailPage,
    ConnectionTypeUpdate,
)
from app.services import references

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
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConnectionTypeDetailPage:
    return await references.connection_type_list(session, params, q)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить тип подключения",
    responses={409: CONNECTION_TYPE_CODE_TAKEN},
)
async def create_connection_type(
    body: ConnectionTypeCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> ConnectionTypeDetail:
    return await references.create_connection_type(session, body)


@router.patch(
    "/{connection_type_id}",
    summary="Изменить тип подключения",
    responses={
        404: {"model": Problem, "description": "Тип подключения не найден"},
        409: CONNECTION_TYPE_CODE_TAKEN,
    },
)
async def update_connection_type(
    connection_type_id: int,
    body: ConnectionTypeUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConnectionTypeDetail:
    connection_type, changes = await references.update_connection_type(
        session, connection_type_id, body
    )
    describe_action(request, changes=changes or None)
    return connection_type
