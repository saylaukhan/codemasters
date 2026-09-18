"""Incident rules of the admin panel (T-40; ТЗ п. 18, п. 20; ADR-007): list, create, change.

A rule is never deleted: it is switched off with ``is_active`` and its incidents keep the
reference. The detection reads the rules anew on every run, so a change applies to the next one
and never rewrites incidents already opened. At least one opening condition stays set: N in a
row or T minutes. The changed fields are returned for the audit record (``describe_action``).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import IncidentRule
from app.schemas.incident_rules import (
    NO_CONDITION,
    IncidentRuleCreate,
    IncidentRuleDetail,
    IncidentRuleDetailPage,
    IncidentRuleUpdate,
)
from app.services.references import Changes, apply_changes, invalid_field, page_of


def rule_detail(rule: IncidentRule) -> IncidentRuleDetail:
    return IncidentRuleDetail.model_validate(rule, from_attributes=True)


async def incident_rule_list(session: AsyncSession, params: PageParams) -> IncidentRuleDetailPage:
    rows, total = await page_of(session, select(IncidentRule).order_by(IncidentRule.id), params)
    return IncidentRuleDetailPage(
        items=[rule_detail(row.IncidentRule) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_incident_rule(
    session: AsyncSession, body: IncidentRuleCreate
) -> IncidentRuleDetail:
    rule = IncidentRule(**body.model_dump())
    session.add(rule)
    await session.commit()
    # ``is_active`` was set by the database: read it back.
    await session.refresh(rule)
    return rule_detail(rule)


async def update_incident_rule(
    session: AsyncSession, rule_id: int, body: IncidentRuleUpdate
) -> tuple[IncidentRuleDetail, Changes]:
    rule = await session.get(IncidentRule, rule_id)
    if rule is None:
        raise ApiError(404, "not_found", "Правило инцидентов не найдено")
    updates = body.model_dump(exclude_unset=True)
    # The body alone cannot tell: clearing N is valid only while T is set, and back.
    count = updates.get("consecutive_violations", rule.consecutive_violations)
    if count is None and updates.get("duration_min", rule.duration_min) is None:
        raise invalid_field("consecutive_violations", NO_CONDITION)
    changes = apply_changes(rule, updates)
    await session.commit()
    return rule_detail(rule), changes
