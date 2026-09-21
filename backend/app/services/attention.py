"""«Требуют внимания» of the main screen (T-60): what asks for a person right now.

Four kinds of row, in the order of docs/design/README.md §4.1: a school with «Нет соединения»,
a school with «Критично», an incident nobody answers for and an appeal the provider has not
moved. The schools come from the same selection as the KPIs and the map, so the filter panel of
T-22 drives this list too, and every query runs in the session of the request, so RLS limits it
to the user's scope (ADR-008). Both windows are settings, never constants: ТЗ п. 11 and п. 20
put such a number into the admin panel (ADR-004).
"""

from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Appeal,
    Device,
    Heartbeat,
    Incident,
    Line,
    Measurement,
    MonitoringPoint,
    Provider,
    Region,
    School,
)
from app.schemas.dashboard import AttentionItem, AttentionPage, AttentionReason
from app.schemas.statuses import IncidentMetric, SchoolStatus
from app.services.appeals.send import SENT_STATUS
from app.services.overview import OverviewFilters, narrow, school_selection
from app.services.settings import system_settings
from app.services.status import WIFI

# Severity of a row and the order of the list: the lower, the worse (docs/design/README.md §4.1).
SEVERITY: dict[AttentionReason, int] = {
    "offline": 1,
    "critical": 2,
    "incident_unassigned": 3,
    "appeal_unanswered": 4,
}

# Status of a school that puts it into the list, and the reason it is there for.
SCHOOL_REASONS: dict[SchoolStatus, AttentionReason] = {"offline": "offline", "critical": "critical"}

# Statuses that take an incident off the list: it is answered, not waiting (ТЗ п. 19, ADR-007).
SETTLED_STATUSES = ("resolved", "closed")


def first_metric(basis_metrics: list[dict[str, Any]]) -> IncidentMetric | None:
    """First basis of the incident: the panel builds the reason in words from it (§4.1)."""
    return basis_metrics[0]["metric"] if basis_metrics else None


def order(item: AttentionItem) -> tuple[int, datetime, int]:
    """Severity first, then the oldest, then the id of the row itself for a stable page."""
    return item.severity, item.since, item.incident_id or item.appeal_id or item.school_id


async def school_items(
    session: AsyncSession, statuses: dict[int, SchoolStatus], *, now: datetime
) -> list[AttentionItem]:
    """Schools with «Нет соединения» or «Критично» and the moment they were last heard from.

    ``since`` is the last signal of the school at ``now`` — a heartbeat, ``last_seen_at`` or a
    measurement of the main line — so the panel can write «нет связи с 09:40» (ADR-014). A school
    that has never said anything falls back to ``now``: there is no earlier moment to name.
    """
    if not statuses:
        return []
    # The first main line of a school names its provider, as the popover of the map does.
    main_line = (
        select(Line.school_id, Line.provider_id)
        .where(Line.status == "main")
        .distinct(Line.school_id)
        .order_by(Line.school_id, Line.id)
        .subquery()
    )
    heard = (
        select(func.max(Heartbeat.ts))
        .where(Heartbeat.device_id == Device.id, Heartbeat.ts <= now)
        .scalar_subquery()
    )
    seen = func.coalesce(case((Device.last_seen_at <= now, Device.last_seen_at)), heard)
    last_seen = (
        select(func.max(seen))
        .select_from(Device)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(MonitoringPoint.school_id == School.id, Device.status == "active")
        .correlate(School)
        .scalar_subquery()
    )
    last_measured = (
        select(func.max(Measurement.measured_at))
        .select_from(Measurement)
        .join(Line, Line.id == Measurement.line_id)
        .where(
            Line.school_id == School.id,
            Line.status == "main",
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.measured_at <= now,
        )
        .correlate(School)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(
            School.id,
            School.school_code,
            School.full_name.label("school_name"),
            Region.name.label("region_name"),
            Provider.name.label("provider_name"),
            func.greatest(last_seen, last_measured).label("since"),
        )
        .join(Region, Region.id == School.region_id)
        .outerjoin(main_line, main_line.c.school_id == School.id)
        .outerjoin(Provider, Provider.id == main_line.c.provider_id)
        .where(School.id.in_(statuses))
    )
    return [
        AttentionItem(
            kind="school",
            reason=SCHOOL_REASONS[statuses[row.id]],
            severity=SEVERITY[SCHOOL_REASONS[statuses[row.id]]],
            school_id=row.id,
            school_code=row.school_code,
            school_name=row.school_name,
            region_name=row.region_name,
            provider_name=row.provider_name,
            status=statuses[row.id],
            incident_id=None,
            incident_number=None,
            appeal_id=None,
            appeal_number=None,
            metric=None,
            since=row.since or now,
        )
        for row in rows
    ]


async def incident_items(
    session: AsyncSession, school_ids: Collection[int], *, older_than: datetime
) -> list[AttentionItem]:
    """Open incidents nobody answers for: no responsible person since ``older_than`` (ADR-007).

    The predicate is written out here instead of the partial index of the detection: that one
    only knows incidents of a rule, and an incident a district opened by hand is exactly the kind
    that is left without a responsible person (T-41).
    """
    rows = await session.execute(
        select(
            Incident.id,
            Incident.number,
            Incident.basis_metrics,
            Incident.started_at,
            Incident.school_id,
            School.school_code,
            School.full_name.label("school_name"),
            Region.name.label("region_name"),
            Provider.name.label("provider_name"),
        )
        .join(School, School.id == Incident.school_id)
        .join(Region, Region.id == School.region_id)
        .join(Provider, Provider.id == Incident.provider_id)
        .where(
            Incident.school_id.in_(school_ids),
            Incident.status.not_in(SETTLED_STATUSES),
            Incident.responsible_user_id.is_(None),
            Incident.started_at <= older_than,
        )
    )
    return [
        AttentionItem(
            kind="incident",
            reason="incident_unassigned",
            severity=SEVERITY["incident_unassigned"],
            school_id=row.school_id,
            school_code=row.school_code,
            school_name=row.school_name,
            region_name=row.region_name,
            provider_name=row.provider_name,
            status=None,
            incident_id=row.id,
            incident_number=row.number,
            appeal_id=None,
            appeal_number=None,
            metric=first_metric(row.basis_metrics),
            since=row.started_at,
        )
        for row in rows
    ]


async def appeal_items(
    session: AsyncSession, school_ids: Collection[int], *, older_than: datetime
) -> list[AttentionItem]:
    """Appeals the provider has not moved: «Передан поставщику» since ``older_than`` (ADR-011).

    There is no event of an answer to look for — ``appeal_events`` records only what the panel
    itself does — so the status the sending wrote is the fact: while it stands, nobody replied.
    """
    rows = await session.execute(
        select(
            Appeal.id,
            Appeal.number,
            Appeal.sent_at,
            Appeal.school_id,
            School.school_code,
            School.full_name.label("school_name"),
            Region.name.label("region_name"),
            Provider.name.label("provider_name"),
        )
        .join(School, School.id == Appeal.school_id)
        .join(Region, Region.id == School.region_id)
        .join(Provider, Provider.id == Appeal.provider_id)
        .where(
            Appeal.school_id.in_(school_ids),
            Appeal.status == SENT_STATUS,
            Appeal.sent_at <= older_than,
        )
    )
    return [
        AttentionItem(
            kind="appeal",
            reason="appeal_unanswered",
            severity=SEVERITY["appeal_unanswered"],
            school_id=row.school_id,
            school_code=row.school_code,
            school_name=row.school_name,
            region_name=row.region_name,
            provider_name=row.provider_name,
            status=None,
            incident_id=None,
            incident_number=None,
            appeal_id=row.id,
            appeal_number=row.number,
            metric=None,
            since=row.sent_at,
        )
        for row in rows
    ]


async def attention_list(
    session: AsyncSession, filters: OverviewFilters, *, now: datetime, limit: int
) -> AttentionPage:
    """Rows that ask for a person at ``now``, the worst first; ``total`` counts them all."""
    settings = await system_settings(session)
    statuses = await school_selection(session, filters, now=now)
    items: list[AttentionItem] = []
    if statuses:
        school_ids = list(statuses)
        items += await school_items(session, narrow(statuses, tuple(SCHOOL_REASONS)), now=now)
        items += await incident_items(
            session,
            school_ids,
            older_than=now - timedelta(hours=settings.attention_incident_unassigned_hours),
        )
        items += await appeal_items(
            session,
            school_ids,
            older_than=now - timedelta(hours=settings.attention_appeal_no_answer_hours),
        )
    items.sort(key=order)
    return AttentionPage(period_to=now, total=len(items), items=items[:limit])
