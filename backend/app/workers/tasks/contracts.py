"""Periodic recompute of the sustained mismatch of main lines with their contract (T-29, ТЗ п. 14).

The rule and its numbers live in ``app/services/status.py`` and ``settings``; the task only
runs it on a schedule of beat and commits. Celery runs as the owner of the tables, outside any
scope, so every line is recomputed (ADR-008).
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.status import recompute_contract_compliance
from app.workers.celery_app import celery_app

RECOMPUTE_CONTRACT_COMPLIANCE = "contracts.recompute_compliance"


async def recompute() -> int:
    # An engine of its own per run: ``asyncio.run`` starts a new event loop every time, and a
    # pooled asyncpg connection cannot outlive the loop it was opened on.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            count = await recompute_contract_compliance(session, now=datetime.now(UTC))
            await session.commit()
            return count
    finally:
        await engine.dispose()


@celery_app.task(name=RECOMPUTE_CONTRACT_COMPLIANCE)
def recompute_contract_compliance_task() -> int:
    """How many main lines got a result."""
    return asyncio.run(recompute())
