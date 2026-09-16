"""Incident rule admin API (plan.md §10 «Админка», ТЗ п. 18, п. 20): list, create, change.

Contract stubs: every endpoint answers 501 until T-40. There is no DELETE: a rule is switched
off with ``is_active`` and its incidents keep the reference (ADR-007). Rules are edited by the
Oblast and Administrator roles (ADR-008 «Открыто»).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.incident_rules import (
    IncidentRuleCreate,
    IncidentRuleDetail,
    IncidentRuleDetailPage,
    IncidentRuleUpdate,
)

router = APIRouter(prefix="/incident-rules", tags=["admin"], dependencies=[Security(user_token)])


@router.get("", summary="Правила формирования инцидентов")
async def list_incident_rules(
    params: Annotated[PageParams, Depends(page_params)],
) -> IncidentRuleDetailPage:
    raise not_implemented("T-40")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать правило инцидентов",
    description="Без consecutive_violations и duration_min — 422.",
)
async def create_incident_rule(body: IncidentRuleCreate) -> IncidentRuleDetail:
    raise not_implemented("T-40")


@router.patch(
    "/{rule_id}",
    summary="Изменить или отключить правило инцидентов",
    description=(
        "Следующая детекция применяет новые значения (T-40). Если после изменения "
        "consecutive_violations и duration_min оба пусты — 422."
    ),
    responses={404: {"model": Problem, "description": "Правило не найдено"}},
)
async def update_incident_rule(rule_id: int, body: IncidentRuleUpdate) -> IncidentRuleDetail:
    raise not_implemented("T-40")
