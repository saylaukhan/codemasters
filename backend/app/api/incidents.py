"""Incident API of the panel (plan.md §7, §10 «Инциденты»; ТЗ п. 19): list, card, manual
creation, status changes and comments.

"CRUD" has no DELETE: an incident and its ``incident_events`` are the history of a problem
(ТЗ п. 19, ADR-007), so status changes and comments only add events; the transitions and the
auto-close live in ``app/services/incident_card.py`` (T-41). Lists and cards are limited by the
user's scope from T-20: a provider sees the incidents of its own lines (ADR-008, T-44).
Incidents of a school card — ``schools.py``.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, current_user, require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.errors import Problem
from app.schemas.incidents import (
    IncidentCommentCreate,
    IncidentCreate,
    IncidentDetail,
    IncidentEventDetail,
    IncidentListItemPage,
    IncidentStatusChange,
    IncidentUpdate,
)
from app.schemas.statuses import IncidentStatus
from app.services import incident_card
from app.services.incident_card import IncidentFilters

router = APIRouter(
    prefix="/incidents", tags=["incidents"], dependencies=[Depends(require("incidents:read"))]
)

INCIDENT_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Инцидент не найден"}


@router.get(
    "",
    summary="Список инцидентов, новые сверху",
    description=(
        "Порядок — по started_at, новые сверху; канбан (T-43) читает этот же список. "
        "Фильтры region_id и provider_id — по школе и линии инцидента."
    ),
)
async def list_incidents(
    params: Annotated[PageParams, Depends(page_params)],
    status: Annotated[
        list[IncidentStatus] | None,
        Query(description="Статусы инцидента; несколько — повтором параметра"),
    ] = None,
    school_id: int | None = None,
    region_id: Annotated[int | None, Query(description="Район или город (regions)")] = None,
    provider_id: int | None = None,
    line_id: int | None = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=32, description="Номер инцидента или его часть")
    ] = None,
    period_from: Annotated[
        AwareDatetime | None, Query(description="Начало периода по started_at, включительно")
    ] = None,
    period_to: Annotated[
        AwareDatetime | None, Query(description="Конец периода по started_at, не включается")
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncidentListItemPage:
    filters = IncidentFilters(
        status, school_id, region_id, provider_id, line_id, q, period_from, period_to
    )
    return await incident_card.incident_list(session, filters, params)


@router.post(
    "",
    dependencies=[Depends(require("incidents:create"))],
    status_code=status.HTTP_201_CREATED,
    summary="Создать инцидент вручную",
    description=(
        "Из карточки школы (ТЗ п. 19): статус new, rule_id = null, событие created в истории; "
        "школа и поставщик — по линии. Неизвестный line_id или responsible_user_id — 422."
    ),
)
async def create_incident(
    body: IncidentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> IncidentDetail:
    incident_id = await incident_card.create_incident(session, body, user, now=datetime.now(UTC))
    return await incident_card.incident_detail(session, incident_id)


@router.get(
    "/{incident_id}",
    summary="Карточка инцидента с историей событий",
    responses={404: INCIDENT_NOT_FOUND},
)
async def get_incident(
    incident_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> IncidentDetail:
    return await incident_card.incident_detail(session, incident_id)


@router.patch(
    "/{incident_id}",
    dependencies=[Depends(require("incidents:update"))],
    summary="Изменить ответственного или описание инцидента",
    description=(
        "Статус меняется только через POST /api/incidents/{incident_id}/status. "
        "Неизвестный responsible_user_id — 422."
    ),
    responses={404: INCIDENT_NOT_FOUND},
)
async def update_incident(
    incident_id: int,
    body: IncidentUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncidentDetail:
    changes = await incident_card.update_incident(session, incident_id, body)
    describe_action(request, changes=changes or None)
    return await incident_card.incident_detail(session, incident_id)


@router.post(
    "/{incident_id}/status",
    dependencies=[Depends(require("incidents:update"))],
    summary="Сменить статус инцидента",
    description=(
        "Переходы (T-41): вперёд по порядку ТЗ п. 19, sent_to_provider, in_progress и "
        "awaiting_info можно пропускать; в closed — только из resolved; назад — только "
        "awaiting_info → in_progress и resolved → in_progress (restored_at сбрасывается); из "
        "closed — никуда. Переход в sent_to_provider ставит sent_to_provider_at, в resolved — "
        "restored_at, если детекция его ещё не поставила, в closed — closed_at. closed ставит "
        "пользователь области или района (ADR-007); resolved → closed через 24 ч — задача beat. "
        "Каждый переход — событие status_change с комментарием."
    ),
    responses={
        404: INCIDENT_NOT_FOUND,
        409: {
            "model": Problem,
            "description": (
                "Переход не допускается, в том числе в текущий статус "
                "(type invalid_status_transition)"
            ),
        },
    },
)
async def change_incident_status(
    incident_id: int,
    body: IncidentStatusChange,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> IncidentDetail:
    changes = await incident_card.change_status(
        session, incident_id, body, user, now=datetime.now(UTC)
    )
    describe_action(request, changes=changes)
    return await incident_card.incident_detail(session, incident_id)


@router.post(
    "/{incident_id}/comments",
    dependencies=[Depends(require("incidents:update"))],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить комментарий к инциденту",
    description="Комментарий — событие comment в истории; статус не меняется.",
    responses={404: INCIDENT_NOT_FOUND},
)
async def create_incident_comment(
    incident_id: int,
    body: IncidentCommentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> IncidentEventDetail:
    return await incident_card.add_comment(
        session, incident_id, body.comment, user, now=datetime.now(UTC)
    )
