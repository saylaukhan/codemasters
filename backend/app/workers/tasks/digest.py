"""Рассылка сводки по расписанию (T-67, docs/design/README.md §6.2).

Задача идёт раз в час и берёт те рассылки, чей день недели и час совпали с текущим моментом в
``settings.timezone``. Отправленные меньше ``RESEND_WINDOW`` назад отсекаются по
``last_sent_at``, а строки читаются ``FOR UPDATE SKIP LOCKED``, поэтому один выпуск не уходит
дважды в одно окно — ни при перезапуске воркера, ни при двух воркерах сразу.

Каждая рассылка коммитится отдельно: SMTP, который не ответил одной школе, не должен отменить
уже отправленные и уже записанные в ``notification_log`` попытки остальных (ТЗ п. 18).
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.digest_admin import due_digests, send_digest
from app.workers.celery_app import celery_app

SEND_DUE_DIGESTS = "digest.send_due"


async def send_due(now: datetime) -> int:
    """Отправить все рассылки, чьё время пришло; сколько выпусков ушло.

    Свой движок на запуск, как в ``tasks/notifications.py``: ``asyncio.run`` каждый раз
    открывает новый цикл событий, а соединение asyncpg из пула его не переживает.
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    sent = 0
    try:
        async with AsyncSession(engine) as session:
            for digest in await due_digests(session, now=now):
                await send_digest(session, digest, now=now)
                await session.commit()
                sent += 1
    finally:
        await engine.dispose()
    return sent


@celery_app.task(name=SEND_DUE_DIGESTS)
def send_due_digests_task() -> dict[str, int]:
    """Сколько выпусков сводки ушло в этот час."""
    return {"sent": asyncio.run(send_due(datetime.now(UTC)))}
