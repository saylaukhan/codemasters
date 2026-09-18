"""Exports of the panel (ТЗ п. 9, plan.md §12): build a file, keep it, serve it to its owner.

A small export is built within ``POST /api/exports`` and is born ``ready``. Every PDF and an
export of more rows than ``settings.export_sync_max_rows`` is born ``pending``: the Celery
worker builds it with ``build_pending_export`` under the scope of its owner (T-33, ADR-008).
Beat removes the exports whose files have expired. Raw measurements come from ``raw.py``,
aggregates per school from ``aggregates.py``, the files from ``files.py``; the PDF report of a
school from ``report.py`` and ``report_pdf.py`` (T-32).
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from fastapi.exceptions import RequestValidationError
from sqlalchemy import ColumnElement, CursorResult, and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.auth.deps import load_user
from app.auth.rls import apply_scope, clear_scope
from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import Export, SystemSettings, User
from app.schemas.exports import ExportCreate, ExportFormat, ExportJob, ExportJobPage
from app.services.exports.aggregates import aggregate_count, aggregate_records
from app.services.exports.columns import AGGREGATE_COLUMN_TITLES, AGGREGATE_COLUMNS
from app.services.exports.files import export_file
from app.services.exports.raw import check_selection, raw_count, raw_records
from app.services.exports.report import school_report
from app.services.exports.report_pdf import report_pdf
from app.services.settings import system_settings

__all__ = [
    "build_pending_export",
    "create_export",
    "fail_export",
    "in_background",
    "owned_export",
    "purge_expired_exports",
    "user_exports",
]

logger = logging.getLogger(__name__)

FILE_PREFIXES = {"raw": "measurements", "aggregates": "schools", "school_report": "report"}

# A file name goes into Content-Disposition as Latin-1: whatever else a School ID has is «_».
UNSAFE_NAME = re.compile(r"[^A-Za-z0-9_-]")

BUILD_FAILED = "Не удалось сформировать файл, попробуйте ещё раз"


@dataclass(frozen=True)
class ExportFile:
    name: str
    content: bytes
    rows_count: int


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


def in_background(file_format: ExportFormat, rows_count: int, sync_max_rows: int) -> bool:
    """Whether Celery builds the file: any PDF, or more rows than the settings allow in the
    request (plan.md §12, «Решения по умолчанию»: больше 10 000 строк или PDF)."""
    return file_format == "pdf" or rows_count > sync_max_rows


async def build_file(
    session: AsyncSession, body: ExportCreate, settings: SystemSettings, *, now: datetime
) -> ExportFile:
    """File of ``body``; the rows are those the session sees, so its scope is the user's."""
    zone = ZoneInfo(settings.timezone)
    if body.mode == "school_report":
        report = await school_report(session, body, zone, settings.timezone, now=now)
        return ExportFile(
            file_name(body, zone, report.school_code), report_pdf(report), len(report.measurements)
        )
    if body.mode == "aggregates":
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
    return ExportFile(file_name(body, zone), content, len(records))


async def create_export(
    session: AsyncSession, user_id: int, body: ExportCreate, *, now: datetime
) -> Export:
    """Export of ``body`` under the user's scope: built at once and ``ready``, or ``pending``
    for the Celery worker when it is a PDF or has too many rows."""
    settings = await system_settings(session)
    await check_selection(session, body)
    # Only the fields of the request: the worker validates them again, and ``columns`` given
    # for a mode other than raw is a 422.
    params = body.model_dump(mode="json", exclude_unset=True)
    export = Export(user_id=user_id, mode=body.mode, format=body.format, params=params)
    if body.mode == "school_report":
        rows_count = 0
    elif body.mode == "aggregates":
        rows_count = await aggregate_count(session, body)
    else:
        rows_count = await raw_count(session, body)
    if in_background(body.format, rows_count, settings.export_sync_max_rows):
        export.status = "pending"
    else:
        built = await build_file(session, body, settings, now=now)
        export.status = "ready"
        export.file_name = built.name
        export.content = built.content
        export.rows_count = built.rows_count
        export.expires_at = now + timedelta(days=settings.export_retention_days)
    session.add(export)
    await session.commit()
    await session.refresh(export, ["created_at"])
    return export


def failure_reason(error: ApiError | RequestValidationError) -> str:
    """What a person reads in the list: the detail of an API error or the first validation one."""
    if isinstance(error, ApiError):
        return error.detail or BUILD_FAILED
    return str(error.errors()[0]["msg"])


async def fail_export(session: AsyncSession, export_id: int, reason: str, *, now: datetime) -> None:
    """Mark the export ``failed`` with ``reason``; it is kept as long as a file would be."""
    export = await session.get_one(Export, export_id)
    settings = await system_settings(session)
    export.status = "failed"
    export.error = reason
    export.expires_at = now + timedelta(days=settings.export_retention_days)
    await session.commit()


async def build_pending_export(session: AsyncSession, export_id: int, *, now: datetime) -> str:
    """Build the file of a pending export as the Celery worker does, under the scope its owner
    has now (ADR-008): a school that left the scope or a blocked account is ``failed``, not a
    file. The session belongs to the owner of the tables; the scope ends with the build.
    Returns the new status; an export already built or removed is left as it is."""
    export = await session.get(Export, export_id)
    if export is None or export.status != "pending":
        return "missing" if export is None else export.status
    user = await session.get_one(User, export.user_id)
    settings = await system_settings(session)
    body = ExportCreate.model_validate(export.params)
    if not user.is_active:
        await fail_export(session, export_id, "Учётная запись заблокирована", now=now)
        return "failed"
    try:
        await apply_scope(session, (await load_user(session, user)).scope)
        try:
            await check_selection(session, body)
            built = await build_file(session, body, settings, now=now)
        finally:
            await clear_scope(session)
    except (ApiError, RequestValidationError) as error:
        await fail_export(session, export_id, failure_reason(error), now=now)
        return "failed"
    except Exception:
        logger.exception("export %s: the file was not built", export_id)
        await session.rollback()
        await fail_export(session, export_id, BUILD_FAILED, now=now)
        raise
    export.status = "ready"
    export.file_name = built.name
    export.content = built.content
    export.rows_count = built.rows_count
    export.expires_at = now + timedelta(days=settings.export_retention_days)
    await session.commit()
    return "ready"


def not_expired(now: datetime) -> ColumnElement[bool]:
    return or_(Export.expires_at.is_(None), Export.expires_at > now)


async def owned_export(
    session: AsyncSession, export_id: int, user_id: int, *, now: datetime
) -> Export:
    """Export of the user with its file; 404 for another user's, an unknown or an expired one."""
    export = await session.scalar(
        select(Export)
        .where(Export.id == export_id, Export.user_id == user_id, not_expired(now))
        .options(undefer(Export.content))
    )
    if export is None:
        raise ApiError(404, "not_found", "Выгрузка не найдена или срок её хранения истёк")
    return export


async def user_exports(
    session: AsyncSession, user_id: int, params: PageParams, *, now: datetime
) -> ExportJobPage:
    """Exports of the user that have not expired, newest first; the files stay unloaded."""
    query = select(Export).where(Export.user_id == user_id, not_expired(now))
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    exports = await session.scalars(
        query.order_by(Export.created_at.desc(), Export.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return ExportJobPage(
        items=[ExportJob.model_validate(export, from_attributes=True) for export in exports],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def purge_expired_exports(session: AsyncSession, *, now: datetime) -> int:
    """Remove the exports whose files have expired, and those still pending after as long as a
    file is kept: their worker is gone. How many were removed."""
    settings = await system_settings(session)
    stale = now - timedelta(days=settings.export_retention_days)
    result = await session.execute(
        delete(Export).where(
            or_(
                Export.expires_at <= now,
                and_(Export.status == "pending", Export.created_at <= stale),
            )
        )
    )
    await session.commit()
    return cast(CursorResult[Any], result).rowcount
