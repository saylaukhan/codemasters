"""Delivery of incident notifications (T-42; ТЗ п. 18; ADR-007).

The task is the only writer of ``notifications``: it runs as the owner of the tables, outside
any scope (ADR-008), because it creates rows that belong to other people — a panel session may
not. The detection of T-40 calls the service directly (it is already in the worker, in its own
session); the panel hands a status change over through ``enqueue_incident_notification`` of
``app/api/incidents.py``, the same way the agent API hands a line to the detection.

A broker that does not answer loses the Telegram and the e-mail of that one change; the incident
itself and its history are already stored, and the next change notifies again.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.notifications import notify_incident
from app.workers.celery_app import celery_app

NOTIFY_INCIDENT = "notifications.incident"


async def notify(incident_id: int, kind: str) -> list[int]:
    # An engine of its own per run, as in ``tasks/incidents.py``: ``asyncio.run`` starts a new
    # event loop every time and a pooled asyncpg connection cannot outlive its loop.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            created = await notify_incident(session, incident_id, kind, now=datetime.now(UTC))
            await session.commit()
            return created
    finally:
        await engine.dispose()


@celery_app.task(name=NOTIFY_INCIDENT)
def notify_incident_task(incident_id: int, kind: str) -> dict[str, int]:
    """How many people were notified about the incident."""
    return {"notified": len(asyncio.run(notify(incident_id, kind)))}
