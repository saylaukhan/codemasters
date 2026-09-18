"""Background exports (T-33, plan.md §12): build a pending file, remove the expired ones.

``POST /api/exports`` hands a PDF or an export of too many rows to ``exports.build``; the file
is built under the scope of its owner (``app/services/exports``, ADR-008). Beat runs
``exports.purge_expired`` every hour: a file lives ``settings.export_retention_days`` days.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.exports import build_pending_export, purge_expired_exports
from app.workers.celery_app import celery_app

BUILD_EXPORT = "exports.build"
PURGE_EXPIRED_EXPORTS = "exports.purge_expired"


async def build(export_id: int) -> str:
    # An engine of its own per run: ``asyncio.run`` starts a new event loop every time, and a
    # pooled asyncpg connection cannot outlive the loop it was opened on.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            return await build_pending_export(session, export_id, now=datetime.now(UTC))
    finally:
        await engine.dispose()


async def purge() -> int:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            return await purge_expired_exports(session, now=datetime.now(UTC))
    finally:
        await engine.dispose()


@celery_app.task(name=BUILD_EXPORT)
def build_export_task(export_id: int) -> str:
    """Status the export ends in: ``ready`` or ``failed``."""
    return asyncio.run(build(export_id))


@celery_app.task(name=PURGE_EXPIRED_EXPORTS)
def purge_expired_exports_task() -> int:
    """How many exports were removed."""
    return asyncio.run(purge())
