"""Incident detection (T-40, ADR-007): after each measurement of a line and every 5 minutes;
the auto-close of resolved incidents (T-41) every 15 minutes.

The rules and the hysteresis live in ``app/services/incidents.py``; the tasks only run them and
commit. ``incidents.detect_line`` is queued by the agent API once new measurements of a line are
stored; beat runs ``incidents.detect_all`` over every watched line, which also catches the
silence of the heartbeat and any measurement whose task was lost. Each line is committed on its
own: a failure on one line does not hold back the others. ``incidents.close_resolved`` closes
the incidents «Устранён» for 24 hours (``app/services/incident_card.py``). Celery runs as the
owner of the tables, outside any scope (ADR-008).
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.incident_card import close_resolved
from app.services.incidents import Detection, detect_line, detection_line_ids
from app.workers.celery_app import celery_app

DETECT_LINE = "incidents.detect_line"
DETECT_ALL = "incidents.detect_all"
CLOSE_RESOLVED = "incidents.close_resolved"

logger = logging.getLogger(__name__)


async def detect_one(line_id: int) -> Detection:
    # An engine of its own per run: ``asyncio.run`` starts a new event loop every time, and a
    # pooled asyncpg connection cannot outlive the loop it was opened on.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            detection = await detect_line(session, line_id, now=datetime.now(UTC))
            await session.commit()
            return detection
    finally:
        await engine.dispose()


async def detect_every() -> Detection:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    total = Detection()
    try:
        async with AsyncSession(engine) as session:
            line_ids = await detection_line_ids(session)
            await session.commit()
            for line_id in line_ids:
                try:
                    total.extend(await detect_line(session, line_id, now=datetime.now(UTC)))
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.exception("incident detection failed on line %s", line_id)
        return total
    finally:
        await engine.dispose()


async def close_every() -> list[int]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            closed = await close_resolved(session, now=datetime.now(UTC))
            await session.commit()
            return closed
    finally:
        await engine.dispose()


def summary(detection: Detection) -> dict[str, int]:
    return {
        "opened": len(detection.opened),
        "updated": len(detection.updated),
        "restored": len(detection.restored),
    }


@celery_app.task(name=DETECT_LINE)
def detect_line_task(line_id: int) -> dict[str, int]:
    """How many incidents of the line were opened, moved on and restored."""
    return summary(asyncio.run(detect_one(line_id)))


@celery_app.task(name=DETECT_ALL)
def detect_all_task() -> dict[str, int]:
    """How many incidents of all lines were opened, moved on and restored."""
    return summary(asyncio.run(detect_every()))


@celery_app.task(name=CLOSE_RESOLVED)
def close_resolved_task() -> dict[str, int]:
    """How many incidents «Устранён» for 24 hours were closed."""
    return {"closed": len(asyncio.run(close_every()))}
