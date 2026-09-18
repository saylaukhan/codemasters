"""Aggregates of an export (T-31, ТЗ п. 9): one record per school of the selection.

The numbers are those of ``GET /api/analytics?level=school`` over the same period (T-27): the
daily aggregate ``m_daily`` (T-19) of the main line, Wi-Fi left out, averages weighted by the
number of measurements, a day that overlaps the period counted whole. ``m_daily`` has no RLS of
its own, so it is reached only through ``lines``, where RLS keeps the user's scope (ADR-008).
A school of the selection without a measurement in the period is still a row, with zeros.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, MDaily, School
from app.schemas.exports import ExportCreate
from app.services.analytics import percent, weighted

DAY = timedelta(days=1)


def rounded(value: float | None) -> float | None:
    """Two decimals: a file is read by a person, not recomputed."""
    return None if value is None else round(float(value), 2)


async def aggregate_records(session: AsyncSession, body: ExportCreate) -> list[dict[str, Any]]:
    """Every aggregate column of every school of the selection, ordered by the school name."""
    lines = (
        select(Line.id.label("line_id"), Line.school_id)
        .join(School, School.id == Line.school_id)
        .where(Line.status == "main")
    )
    if body.school_ids:
        lines = lines.where(School.id.in_(body.school_ids))
    else:
        lines = lines.where(School.is_active)
    selected = lines.subquery()

    measured = (
        select(
            selected.c.school_id,
            func.sum(MDaily.measurements_count).label("measurements_count"),
            func.sum(MDaily.problem_count).label("problem_count"),
            weighted(MDaily.avg_download_mbps, MDaily.measurements_count).label(
                "avg_download_mbps"
            ),
            func.min(MDaily.min_download_mbps).label("min_download_mbps"),
            weighted(MDaily.avg_upload_mbps, MDaily.measurements_count).label("avg_upload_mbps"),
            weighted(MDaily.avg_ping_ms, MDaily.measurements_count).label("avg_ping_ms"),
        )
        .join(selected, selected.c.line_id == MDaily.line_id)
        .where(MDaily.bucket > body.period_from - DAY, MDaily.bucket < body.period_to)
        .group_by(selected.c.school_id)
        .subquery()
    )
    query = (
        select(School.school_code, School.full_name, measured)
        .outerjoin(measured, measured.c.school_id == School.id)
        .where(School.id.in_(select(selected.c.school_id)))
        .order_by(School.full_name, School.id)
    )

    records = []
    for row in await session.execute(query):
        count = int(row.measurements_count or 0)
        problems = int(row.problem_count or 0)
        records.append(
            {
                "school_code": row.school_code,
                "school_name": row.full_name,
                "measurements_count": count,
                "avg_download_mbps": rounded(row.avg_download_mbps),
                "min_download_mbps": rounded(row.min_download_mbps),
                "avg_upload_mbps": rounded(row.avg_upload_mbps),
                "avg_ping_ms": rounded(row.avg_ping_ms),
                "problem_count": problems,
                "problem_pct": rounded(percent(problems, count)),
            }
        )
    return records
