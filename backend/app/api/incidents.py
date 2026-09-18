"""Incident API of the panel (plan.md §7, §10 «Инциденты»; ТЗ п. 19): list, card, manual
creation, status changes and comments.

Contract stubs: every endpoint answers 501 until T-41. "CRUD" has no DELETE: an incident and its
``incident_events`` are the history of a problem (ТЗ п. 19, ADR-007), so status changes and
comments only add events. Lists and cards are limited by the user's scope from T-20: a provider
sees the incidents of its own lines (ADR-008, T-44). Incidents of a school card — ``schools.py``.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime

from app.auth import require
from app.core.deps import PageParams, page_params
from app.core.errors import not_implemented
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
) -> IncidentListItemPage:
    raise not_implemented("T-41")


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
async def create_incident(body: IncidentCreate) -> IncidentDetail:
    raise not_implemented("T-41")


@router.get(
    "/{incident_id}",
    summary="Карточка инцидента с историей событий",
    responses={404: INCIDENT_NOT_FOUND},
)
async def get_incident(incident_id: int) -> IncidentDetail:
    raise not_implemented("T-41")


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
async def update_incident(incident_id: int, body: IncidentUpdate) -> IncidentDetail:
    raise not_implemented("T-41")


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
async def change_incident_status(incident_id: int, body: IncidentStatusChange) -> IncidentDetail:
    raise not_implemented("T-41")


@router.post(
    "/{incident_id}/comments",
    dependencies=[Depends(require("incidents:update"))],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить комментарий к инциденту",
    description="Комментарий — событие comment в истории; статус не меняется.",
    responses={404: INCIDENT_NOT_FOUND},
)
async def create_incident_comment(
    incident_id: int, body: IncidentCommentCreate
) -> IncidentEventDetail:
    raise not_implemented("T-41")
