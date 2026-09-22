"""Incident rules of the admin panel (T-40, T-85; ТЗ п. 18, п. 20; ADR-007): list, create, change.

A rule is never deleted: it is switched off with ``is_active`` and its incidents keep the
reference. The detection reads the rules anew on every run, so a change applies to the next one
and never rewrites incidents already opened. At least one opening condition stays set: N in a
row or T minutes. A rule of a school names an existing school; the school itself is looked up
in the session of the request, so a school outside the scope is unknown here (ADR-008). The
changed fields are returned for the audit record (``describe_action``).
"""

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import IncidentRule, School
from app.schemas.incident_rules import (
    NO_CONDITION,
    IncidentRuleCreate,
    IncidentRuleDetail,
    IncidentRuleDetailPage,
    IncidentRuleScope,
    IncidentRuleUpdate,
)
from app.services.references import Changes, apply_changes, invalid_field, matching, page_of


def rule_rows() -> Select[Any]:
    """Rules with the School ID and the name of their school; empty for a rule of the oblast."""
    return select(
        IncidentRule, School.school_code, School.full_name.label("school_name")
    ).outerjoin(School, School.id == IncidentRule.school_id)


def rule_detail(row: Any) -> IncidentRuleDetail:
    rule: IncidentRule = row.IncidentRule
    return IncidentRuleDetail.model_validate(
        {
            "id": rule.id,
            "name": rule.name,
            "metric": rule.metric,
            "scope": rule.scope,
            "school_id": rule.school_id,
            "school_code": row.school_code,
            "school_name": row.school_name,
            "consecutive_violations": rule.consecutive_violations,
            "duration_min": rule.duration_min,
            "recovery_normal_count": rule.recovery_normal_count,
            "is_active": rule.is_active,
        }
    )


async def one_rule(session: AsyncSession, rule_id: int) -> IncidentRuleDetail:
    row = (await session.execute(rule_rows().where(IncidentRule.id == rule_id))).one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Правило инцидентов не найдено")
    return rule_detail(row)


async def incident_rule_list(
    session: AsyncSession,
    params: PageParams,
    *,
    scope: IncidentRuleScope | None = None,
    school_id: int | None = None,
    q: str | None = None,
) -> IncidentRuleDetailPage:
    """Rules of the oblast first, then the rules of schools by the name of the school."""
    query = rule_rows().where(*matching(q, IncidentRule.name, School.full_name, School.school_code))
    if scope is not None:
        query = query.where(IncidentRule.scope == scope)
    if school_id is not None:
        query = query.where(IncidentRule.school_id == school_id)
    # ``global`` sorts before ``school``: the rules of the oblast come first.
    query = query.order_by(IncidentRule.scope, School.full_name, IncidentRule.id)
    rows, total = await page_of(session, query, params)
    return IncidentRuleDetailPage(
        items=[rule_detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_incident_rule(
    session: AsyncSession, body: IncidentRuleCreate
) -> IncidentRuleDetail:
    if body.school_id is not None and await session.get(School, body.school_id) is None:
        raise invalid_field("school_id", "Школа не найдена")
    rule = IncidentRule(**body.model_dump())
    session.add(rule)
    await session.commit()
    return await one_rule(session, rule.id)


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
    return await one_rule(session, rule_id), changes
