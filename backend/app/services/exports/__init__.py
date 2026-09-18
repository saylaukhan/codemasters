"""Exports of the panel (ТЗ п. 9, plan.md §12): build a file, keep it, serve it to its owner.

Until T-33 the file is built within ``POST /api/exports``, so an export is born ``ready``.
Raw measurements come from ``raw.py``, the files from ``files.py``; aggregates per school are
T-31, the PDF report of a school is T-32.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.errors import ApiError, not_implemented
from app.models import Export
from app.schemas.exports import ExportCreate
from app.services.exports.files import export_file
from app.services.exports.raw import check_selection, raw_records
from app.services.settings import system_settings

__all__ = ["create_export", "owned_export"]

MODE_TASKS = {"aggregates": "T-31", "school_report": "T-32"}


def file_name(body: ExportCreate, zone: ZoneInfo) -> str:
    """``measurements_<first day>_<last day>.<format>``: days of the period in local time; the
    end of the period is exclusive."""
    first = body.period_from.astimezone(zone).date()
    last = (body.period_to - timedelta(microseconds=1)).astimezone(zone).date()
    return f"measurements_{first.isoformat()}_{last.isoformat()}.{body.format}"


async def create_export(
    session: AsyncSession, user_id: int, body: ExportCreate, *, now: datetime
) -> Export:
    """Build the file of ``body`` under the user's scope and store it as a ready export."""
    if body.mode in MODE_TASKS:
        raise not_implemented(MODE_TASKS[body.mode])
    settings = await system_settings(session)
    zone = ZoneInfo(settings.timezone)
    await check_selection(session, body)
    records = await raw_records(session, body, zone)
    export = Export(
        user_id=user_id,
        mode=body.mode,
        format=body.format,
        status="ready",
        params=body.model_dump(mode="json"),
        rows_count=len(records),
        file_name=file_name(body, zone),
        content=export_file(body.format, body.columns, records),
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
