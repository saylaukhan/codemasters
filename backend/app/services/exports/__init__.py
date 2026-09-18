"""Exports of the panel (ТЗ п. 9, plan.md §12): build a file, keep it, serve it to its owner.

Until T-33 the file is built within ``POST /api/exports``, so an export is born ``ready``.
Raw measurements come from ``raw.py``, aggregates per school from ``aggregates.py``, the files
from ``files.py``; the PDF report of a school from ``report.py`` and ``report_pdf.py`` (T-32).
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.errors import ApiError
from app.models import Export
from app.schemas.exports import ExportCreate
from app.services.exports.aggregates import aggregate_records
from app.services.exports.columns import AGGREGATE_COLUMN_TITLES, AGGREGATE_COLUMNS
from app.services.exports.files import export_file
from app.services.exports.raw import check_selection, raw_records
from app.services.exports.report import school_report
from app.services.exports.report_pdf import report_pdf
from app.services.settings import system_settings

__all__ = ["create_export", "owned_export"]

FILE_PREFIXES = {"raw": "measurements", "aggregates": "schools", "school_report": "report"}

# A file name goes into Content-Disposition as Latin-1: whatever else a School ID has is «_».
UNSAFE_NAME = re.compile(r"[^A-Za-z0-9_-]")


def file_name(body: ExportCreate, zone: ZoneInfo, school_code: str | None = None) -> str:
    """``measurements_<first day>_<last day>.<format>`` (``schools_…`` for aggregates,
    ``report_<School ID>_…`` for the report): days of the period in local time; the end of the
    period is exclusive."""
    first = body.period_from.astimezone(zone).date()
    last = (body.period_to - timedelta(microseconds=1)).astimezone(zone).date()
    prefix = FILE_PREFIXES[body.mode]
    if school_code is not None:
        prefix = f"{prefix}_{UNSAFE_NAME.sub('_', school_code)}"
    return f"{prefix}_{first.isoformat()}_{last.isoformat()}.{body.format}"


async def create_export(
    session: AsyncSession, user_id: int, body: ExportCreate, *, now: datetime
) -> Export:
    """Build the file of ``body`` under the user's scope and store it as a ready export."""
    settings = await system_settings(session)
    zone = ZoneInfo(settings.timezone)
    await check_selection(session, body)
    name = file_name(body, zone)
    if body.mode == "school_report":
        report = await school_report(session, body, zone, settings.timezone, now=now)
        records = report.measurements
        content = report_pdf(report)
        name = file_name(body, zone, report.school_code)
    elif body.mode == "aggregates":
        records = await aggregate_records(session, body)
        content = export_file(
            body.format,
            AGGREGATE_COLUMNS,
            records,
            titles=AGGREGATE_COLUMN_TITLES,
            sheet_name="Школы",
        )
    else:
        records = await raw_records(session, body, zone)
        content = export_file(body.format, body.columns, records)
    export = Export(
        user_id=user_id,
        mode=body.mode,
        format=body.format,
        status="ready",
        params=body.model_dump(mode="json"),
        rows_count=len(records),
        file_name=name,
        content=content,
        expires_at=now + timedelta(days=settings.export_retention_days),
    )
    session.add(export)
    await session.commit()
    await session.refresh(export, ["created_at"])
    return export


async def owned_export(
    session: AsyncSession, export_id: int, user_id: int, *, now: datetime
) -> Export:
    """Export of the user with its file; 404 for another user's, an unknown or an expired one."""
    export = await session.scalar(
        select(Export)
        .where(Export.id == export_id, Export.user_id == user_id)
        .options(undefer(Export.content))
    )
    if export is None or (export.expires_at is not None and export.expires_at <= now):
        raise ApiError(404, "not_found", "Выгрузка не найдена или срок её хранения истёк")
    return export
