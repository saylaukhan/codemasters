"""Календарь каникул, праздников и плановых работ (T-70, docs/design/README.md §6.5).

Раздел администрирования, поэтому право одно — ``schedules:manage``, как у расписаний замеров:
календарь задаёт, когда мониторинг молчит, ровно так же, как расписание задаёт, когда он
измеряет. Какие события видит и правит запрос, решает область видимости и RLS: район работает
со своими событиями и видит события области (ADR-008, миграция T-70).
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventDetail,
    CalendarEventDetailPage,
    CalendarEventUpdate,
    CalendarImportRequest,
    CalendarImportResult,
    CalendarKind,
)
from app.schemas.errors import Problem
from app.services import calendar_admin

router = APIRouter(
    prefix="/calendar", tags=["admin"], dependencies=[Depends(require("schedules:manage"))]
)

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem, "description": "Событие календаря не найдено"}
}


@router.get(
    "",
    summary="События календаря: каникулы, праздники, плановые работы",
    description=(
        "Ближайшие сверху. В каникулы и праздники доступность не считается и инциденты не "
        "создаются, окно плановых работ не входит в оценку поставщика (ТЗ п. 14)."
    ),
)
async def list_calendar_events(
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: CalendarKind | None = None,
    period_from: Annotated[datetime | None, Query(description="Конец события позже этого")] = None,
    period_to: Annotated[
        datetime | None, Query(description="Начало события не позже этого")
    ] = None,
) -> CalendarEventDetailPage:
    return await calendar_admin.calendar_list(session, params, kind, period_from, period_to)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить событие календаря",
    description=(
        "scope=oblast — вся область, scope=district — район (обязателен region_id), "
        "scope=school — школа (обязателен school_id). provider_id указывается только при "
        "kind=planned_works. Границы каникул и праздника — целые местные сутки."
    ),
)
async def create_calendar_event(
    body: CalendarEventCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> CalendarEventDetail:
    return await calendar_admin.create_event(session, body)


@router.patch(
    "/{event_id}",
    summary="Изменить событие календаря",
    description="Тип и цель события не меняются: для другой цели заведите новое событие.",
    responses=NOT_FOUND,
)
async def update_calendar_event(
    event_id: int,
    body: CalendarEventUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CalendarEventDetail:
    event, changes = await calendar_admin.update_event(session, event_id, body)
    describe_action(request, changes=changes or None)
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить событие календаря",
    description="Событие — настройка, а не история: удаление ничего не теряет.",
    responses=NOT_FOUND,
)
async def delete_calendar_event(
    event_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    await calendar_admin.delete_event(session, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/import",
    summary="Импорт календаря из таблицы",
    description=(
        "Содержимое файла CSV с заголовком kind,title,start,end и необязательными school_code, "
        "region_code и comment. Дата YYYY-MM-DD — целые местные сутки, последний день входит "
        "целиком. Строка с ошибкой не останавливает импорт: она возвращается в errors."
    ),
)
async def import_calendar(
    body: CalendarImportRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> CalendarImportResult:
    return await calendar_admin.import_calendar(session, body)
