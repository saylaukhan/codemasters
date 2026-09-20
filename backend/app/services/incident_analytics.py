"""Incidents of the analytics (T-45; ТЗ п. 19; plan.md §7; ADR-007): how many, how long, how often.

Rows stand on the same selection of lines as the report of T-27, so the filters, the scope (RLS
on ``lines`` and ``schools``, ADR-008) and the rule that main and reserve lines never mix hold
here too. An incident falls into the period by ``started_at``; its length is
``restored_at − started_at`` as in the card of T-41, so an incident that is still open counts
but lengthens nothing. Repeatability is the incidents of one line brought to 30 days: periods of
different length stay comparable (plan.md §7).
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident
from app.schemas.analytics import (
    AnalyticsLevel,
    AnalyticsPeriod,
    IncidentAnalyticsReport,
    IncidentAnalyticsRow,
)
from app.services.analytics import (
    AnalyticsFilters,
    level_entities,
    level_key,
    period_bounds,
    selected_lines,
)
from app.services.settings import system_settings

# Window the repeatability is brought to (plan.md §7): incidents of one line per 30 days.
REPEATABILITY_WINDOW = timedelta(days=30)


def seconds(value: Any) -> int | None:
    """Whole seconds of an aggregate; the database answers with a float or a Decimal."""
    return None if value is None else int(round(float(value)))


async def incident_analytics_report(
    session: AsyncSession,
    level: AnalyticsLevel,
    filters: AnalyticsFilters,
    *,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    now: datetime,
) -> IncidentAnalyticsReport:
    settings = await system_settings(session)
    start, end = period_bounds(period, period_from, period_to, now=now, timezone=settings.timezone)
    selected = selected_lines(filters).subquery()
    key = level_key(level, selected)

    # Length of a restored incident; an open one is null and neither sums nor averages.
    duration = extract("epoch", Incident.restored_at - Incident.started_at)
    counted = (
        select(
            func.count(func.distinct(selected.c.line_id)).label("lines_count"),
            func.count(Incident.id).label("incidents_count"),
            func.count(Incident.id).filter(Incident.restored_at.is_(None)).label("open_count"),
            func.count(Incident.restored_at).label("restored_count"),
            func.sum(duration).label("total_duration_s"),
            func.max(duration).label("max_duration_s"),
        )
        .select_from(selected)
        # An outer join keeps the lines without a single incident: their row is zeros, not a gap.
        .outerjoin(
            Incident,
            and_(
                Incident.line_id == selected.c.line_id,
                Incident.started_at >= start,
                Incident.started_at < end,
            ),
        )
    )
    if key is not None:
        counted = counted.add_columns(key.label("key")).group_by(key)
    counted_rows = {getattr(row, "key", None): row for row in await session.execute(counted)}

    def repeatability(lines_count: int, incidents_count: int) -> float | None:
        if not lines_count:
            return None
        return incidents_count / lines_count * (REPEATABILITY_WINDOW / (end - start))

    rows = []
    for entity_id, name in await level_entities(session, level, selected):
        row = counted_rows.get(entity_id)
        lines_count = int(row.lines_count) if row else 0
        incidents_count = int(row.incidents_count) if row else 0
        restored_count = int(row.restored_count) if row else 0
        total_duration_s = seconds(row.total_duration_s) if row and restored_count else None
        rows.append(
            IncidentAnalyticsRow(
                id=entity_id,
                name=name,
                lines_count=lines_count,
                incidents_count=incidents_count,
                open_count=int(row.open_count) if row else 0,
                restored_count=restored_count,
                total_duration_s=total_duration_s,
                avg_duration_s=(
                    round(total_duration_s / restored_count)
                    if total_duration_s is not None and restored_count
                    else None
                ),
                max_duration_s=seconds(row.max_duration_s) if row and restored_count else None,
                incidents_per_line_30d=repeatability(lines_count, incidents_count),
            )
        )

    return IncidentAnalyticsReport(
        period_from=start,
        period_to=end,
        repeatability_window_days=REPEATABILITY_WINDOW.days,
        rows=rows,
    )
