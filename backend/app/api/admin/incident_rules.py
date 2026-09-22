"""Incident rule admin API (plan.md §10 «Админка», ТЗ п. 18, п. 20): list, create, change.

There is no DELETE: a rule is switched off with ``is_active`` and its incidents keep the
reference (ADR-007). The detection of T-40 applies a change from its next run. A rule of the
oblast watches every line; a rule of a school replaces it for the lines of that school (T-59).
Rules are edited by the Oblast and Administrator roles (ADR-008 «Открыто»); every change goes
to the audit log.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.errors import Problem
from app.schemas.incident_rules import (
    IncidentRuleCreate,
    IncidentRuleDetail,
    IncidentRuleDetailPage,
    IncidentRuleScope,
    IncidentRuleUpdate,
)
from app.services import incident_rules

router = APIRouter(
    prefix="/incident-rules",
    tags=["admin"],
    dependencies=[Depends(require("incident_rules:manage"))],
)


@router.get(
    "",
    summary="Правила формирования инцидентов",
    description=(
        "Порядок: правила области, затем правила школ по названию школы. Правило школы "
        "заменяет для её линий правило области по тому же показателю (T-59)."
    ),
)
async def list_incident_rules(
    params: Annotated[PageParams, Depends(page_params)],
    scope: IncidentRuleScope | None = None,
    school_id: int | None = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=255, description="Название правила, школа или School ID"),
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncidentRuleDetailPage:
    return await incident_rules.incident_rule_list(
        session, params, scope=scope, school_id=school_id, q=q
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать правило инцидентов",
    description=(
        "Без consecutive_violations и duration_min — 422. Для scope=school обязателен "
        "school_id; неизвестная школа — 422."
    ),
)
async def create_incident_rule(
    body: IncidentRuleCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> IncidentRuleDetail:
    return await incident_rules.create_incident_rule(session, body)


@router.patch(
    "/{rule_id}",
    summary="Изменить или отключить правило инцидентов",
    description=(
        "Следующая детекция применяет новые значения (T-40). Если после изменения "
        "consecutive_violations и duration_min оба пусты — 422. Показатель, уровень и школа "
        "правила не меняются: другая цель — новое правило."
    ),
    responses={404: {"model": Problem, "description": "Правило не найдено"}},
)
async def update_incident_rule(
    rule_id: int,
    body: IncidentRuleUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncidentRuleDetail:
    rule, changes = await incident_rules.update_incident_rule(session, rule_id, body)
    describe_action(request, changes=changes or None)
    return rule
