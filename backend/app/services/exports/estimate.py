"""Rows an export would have, before its file is built (T-64, DESIGN.md §3.24).

The count never walks ``measurements``: the aggregates answer it. For ``aggregates`` it is the
number of schools the file would hold and it is exact; for ``raw`` it is the sum of the daily
counters of ``m_daily`` (T-19) over the lines of the selection and it is an estimate — Wi-Fi
measurements are not in ``m_daily`` (ADR-012) and a day the period only touches is counted
whole. ``m_daily`` has no RLS of its own, so it is reached only through ``lines``, where RLS
keeps the user's scope (ADR-008).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, MDaily, School
from app.schemas.exports import ExportCreate, ExportEstimate, ExportEstimateQuery
from app.schemas.statuses import QualityStatus
from app.services.exports.aggregates import DAY, aggregate_count
from app.services.exports.raw import check_selection

# Statuses ``m_daily`` counts in ``problem_count``: everything but «Норма» (ADR-004).
PROBLEM_STATUSES: frozenset[QualityStatus] = frozenset({"unstable", "critical", "offline"})


def selected_lines(body: ExportCreate) -> Select[Any]:
    """Lines whose measurements a raw file would hold: those of the chosen schools, or every
    line of the scope. Line statuses are not filtered — ``raw_query`` does not filter them."""
    lines = select(Line.id.label("line_id")).join(School, School.id == Line.school_id)
    if body.school_ids:
        return lines.where(School.id.in_(body.school_ids))
    return lines


def counted_rows(statuses: Sequence[QualityStatus]) -> ColumnElement[int]:
    """Counter of ``m_daily`` that matches the status filter of ``raw_query``: problems only,
    «Норма» only, or every measurement for a mix and for no filter."""
    asked = set(statuses)
    if asked and asked <= PROBLEM_STATUSES:
        return func.sum(MDaily.problem_count)
    if asked == {"normal"}:
        return func.sum(MDaily.measurements_count - MDaily.problem_count)
    return func.sum(MDaily.measurements_count)


async def raw_estimate(session: AsyncSession, body: ExportCreate) -> int:
    """Measurements a raw file of ``body`` would hold, counted over the daily aggregates."""
    lines = selected_lines(body).subquery()
    query = (
        select(counted_rows(body.statuses))
        .join(lines, lines.c.line_id == MDaily.line_id)
        .where(MDaily.bucket > body.period_from - DAY, MDaily.bucket < body.period_to)
    )
    if body.device_ids:
        query = query.where(MDaily.device_id.in_(body.device_ids))
    return int(await session.scalar(query) or 0)


async def export_estimate(session: AsyncSession, query: ExportEstimateQuery) -> ExportEstimate:
    """Rows the file of ``query`` would have, without building it; an unknown or out-of-scope
    school or computer is the same 422 as in ``POST /api/exports`` (ADR-008)."""
    body = query.selection()
    await check_selection(session, body)
    if body.mode == "aggregates":
        rows_count, exact = await aggregate_count(session, body), True
    else:
        rows_count, exact = await raw_estimate(session, body), False
    return ExportEstimate(
        mode=query.mode,
        period_from=query.period_from,
        period_to=query.period_to,
        rows_count=rows_count,
        exact=exact,
    )
