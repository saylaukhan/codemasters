"""Рассылки сводки в админке и сама отправка (T-67; ТЗ п. 18; docs/design/README.md §6.2).

CRUD повторяет дом остальных настроек (``config_admin.py``): список с наименованием района,
создание, PATCH только присутствующих полей, изменённые поля — в журнал аудита. Удаление здесь
есть, в отличие от профилей и расписаний: рассылка — это настройка, а не история, и миграция
T-67 выдаёт роли панели DELETE на одну эту таблицу.

Отправка — второй половина задачи. Письмо с PDF и короткое сообщение в Telegram не обязательны
по отдельности, но каждая попытка каждого канала попадает в ``notification_log`` вместе с
причиной, по которой она не удалась или была пропущена (ТЗ п. 18, инвариант 10 AGENTS.md §8).
``notification_log.notification_id`` — NOT NULL, поэтому отправка сначала создаёт свою строку
``notifications`` вида ``digest_sent``: у неё нет ни пользователя, ни инцидента, и колокольчик
панели её не показывает. Установка без SMTP — нормальная установка: канал пишется как
``skipped``, запрос не падает.
"""

import asyncio
import logging
import smtplib
import urllib.error
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import DigestSettings, Notification, NotificationLog, Region
from app.schemas.digests import (
    DigestDelivery,
    DigestSendResult,
    DigestSettingsCreate,
    DigestSettingsDetail,
    DigestSettingsDetailPage,
    DigestSettingsUpdate,
)
from app.services.digest import Digest, build_digest, digest_file_name, digest_message, digest_pdf
from app.services.notifications import (
    CHANNEL_OFF,
    NO_ADDRESS,
    Delivery,
    send_email,
    send_telegram,
)
from app.services.references import Changes, apply_changes, ensure_region, page_of
from app.services.settings import system_settings

logger = logging.getLogger(__name__)

NOT_FOUND = "Рассылка сводки не найдена"

# Заголовок строки ``notifications`` отправки: текст хранится вместе с ней и не меняется.
DIGEST_KIND = "digest_sent"

# Окно, внутри которого один и тот же выпуск повторно не уходит: перезапуск воркера в тот же
# час не должен отправить сводку дважды, а следующая неделя наступает много позже.
RESEND_WINDOW = timedelta(hours=12)


# --- Список и правка -----------------------------------------------------------------------


def digest_rows() -> Select[Any]:
    """Рассылки с наименованием их района."""
    return select(DigestSettings, Region.name.label("region_name")).outerjoin(
        Region, Region.id == DigestSettings.region_id
    )


def digest_detail(row: Any) -> DigestSettingsDetail:
    digest: DigestSettings = row.DigestSettings
    return DigestSettingsDetail.model_validate(
        {
            "id": digest.id,
            "scope": digest.scope,
            "region_id": digest.region_id,
            "region_name": row.region_name,
            "weekday": digest.weekday,
            "hour": digest.hour,
            "recipients": digest.recipients,
            "telegram_chat_id": digest.telegram_chat_id,
            "is_active": digest.is_active,
            "last_sent_at": digest.last_sent_at,
        }
    )


async def digest_list(session: AsyncSession, params: PageParams) -> DigestSettingsDetailPage:
    query = digest_rows().order_by(DigestSettings.scope, Region.name, DigestSettings.id)
    rows, total = await page_of(session, query, params)
    return DigestSettingsDetailPage(
        items=[digest_detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def digest_row(session: AsyncSession, digest_id: int) -> Any:
    row = (await session.execute(digest_rows().where(DigestSettings.id == digest_id))).one_or_none()
    if row is None:
        raise ApiError(404, "not_found", NOT_FOUND)
    return row


async def create_digest(session: AsyncSession, body: DigestSettingsCreate) -> DigestSettingsDetail:
    if body.region_id is not None:
        await ensure_region(session, body.region_id)
    digest = DigestSettings(**body.model_dump())
    session.add(digest)
    await session.commit()
    return await digest_detail_by_id(session, digest.id)


async def digest_detail_by_id(session: AsyncSession, digest_id: int) -> DigestSettingsDetail:
    return digest_detail(await digest_row(session, digest_id))


async def update_digest(
    session: AsyncSession, digest_id: int, body: DigestSettingsUpdate
) -> tuple[DigestSettingsDetail, Changes]:
    digest: DigestSettings = (await digest_row(session, digest_id)).DigestSettings
    changes = apply_changes(digest, body.model_dump(exclude_unset=True))
    await session.commit()
    return await digest_detail_by_id(session, digest_id), changes


async def delete_digest(session: AsyncSession, digest_id: int) -> None:
    """Рассылку можно удалить: это настройка, а не история (миграция T-67)."""
    digest: DigestSettings = (await digest_row(session, digest_id)).DigestSettings
    await session.delete(digest)
    await session.commit()


# --- Отправка ------------------------------------------------------------------------------


async def digest_of_row(session: AsyncSession, digest: DigestSettings, *, now: datetime) -> Digest:
    return await build_digest(session, region_id=digest.region_id, now=now)


async def deliver_email(
    settings: Settings, address: str, subject: str, text: str, pdf: tuple[str, bytes]
) -> Delivery:
    if not settings.smtp_host:
        return Delivery("email", "skipped", address, CHANNEL_OFF)
    try:
        await asyncio.to_thread(send_email, settings, address, subject, text, pdf)
    except (OSError, smtplib.SMTPException) as error:
        logger.warning("сводка не ушла на %s: %s", address, error)
        return Delivery("email", "failed", address, str(error))
    return Delivery("email", "sent", address)


async def deliver_telegram(settings: Settings, chat_id: str, text: str) -> Delivery:
    if not settings.telegram_bot_token:
        return Delivery("telegram", "skipped", chat_id, CHANNEL_OFF)
    try:
        await asyncio.to_thread(send_telegram, settings.telegram_bot_token, chat_id, text)
    except (OSError, urllib.error.URLError, RuntimeError) as error:
        logger.warning("сводка не ушла в чат %s: %s", chat_id, error)
        return Delivery("telegram", "failed", chat_id, str(error))
    return Delivery("telegram", "sent", chat_id)


async def send_digest(
    session: AsyncSession, digest: DigestSettings, *, now: datetime
) -> DigestSendResult:
    """Собрать выпуск, отправить его по каналам рассылки и записать каждую попытку.

    Вызывающий коммитит. Строка ``notifications`` создаётся всегда: без неё журналу не на чем
    держаться (ТЗ п. 18).
    """
    issue = await digest_of_row(session, digest, now=now)
    pdf = digest_pdf(issue)
    subject, body = digest_message(issue)
    settings = get_settings()

    notification = Notification(
        kind=DIGEST_KIND, title=subject, body=body, created_at=now, updated_at=now
    )
    session.add(notification)
    await session.flush()

    deliveries: list[Delivery] = []
    if digest.recipients:
        attachment = (digest_file_name(issue), pdf)
        for address in digest.recipients:
            deliveries.append(await deliver_email(settings, address, subject, body, attachment))
    else:
        deliveries.append(Delivery("email", "skipped", None, NO_ADDRESS))
    if digest.telegram_chat_id:
        deliveries.append(
            await deliver_telegram(settings, digest.telegram_chat_id, f"{subject}\n{body}")
        )

    for item in deliveries:
        session.add(
            NotificationLog(
                notification_id=notification.id,
                channel=item.channel,
                result=item.result,
                target=item.target,
                error=item.error,
                created_at=now,
            )
        )
    digest.last_sent_at = now
    await session.flush()
    return DigestSendResult(
        sent_at=now,
        deliveries=[
            DigestDelivery.model_validate(item, from_attributes=True) for item in deliveries
        ],
    )


async def send_digest_now(
    session: AsyncSession, digest_id: int, *, now: datetime
) -> DigestSendResult:
    """«Отправить сейчас»: тот же выпуск вне расписания, с тем же журналом."""
    digest: DigestSettings = (await digest_row(session, digest_id)).DigestSettings
    result = await send_digest(session, digest, now=now)
    await session.commit()
    return result


async def digest_preview(
    session: AsyncSession, digest_id: int, *, now: datetime
) -> tuple[bytes, str]:
    """PDF предпросмотра: тот же генератор, что письмо, — файл и его имя (§6.2)."""
    digest: DigestSettings = (await digest_row(session, digest_id)).DigestSettings
    issue = await digest_of_row(session, digest, now=now)
    return digest_pdf(issue), digest_file_name(issue)


async def due_digests(session: AsyncSession, *, now: datetime) -> list[DigestSettings]:
    """Включённые рассылки, чей день недели и час совпали с ``now`` в зоне системы.

    Строки берутся ``FOR UPDATE SKIP LOCKED``, а отправленные меньше ``RESEND_WINDOW`` назад
    отсекаются по ``last_sent_at``: один выпуск не уходит дважды в одно окно, даже если воркер
    перезапустился внутри того же часа.
    """
    settings = await system_settings(session)
    local = now.astimezone(ZoneInfo(settings.timezone))
    rows = await session.scalars(
        select(DigestSettings)
        .where(
            DigestSettings.is_active,
            DigestSettings.weekday == local.isoweekday(),
            DigestSettings.hour == local.hour,
            (DigestSettings.last_sent_at.is_(None))
            | (DigestSettings.last_sent_at < now - RESEND_WINDOW),
        )
        .order_by(DigestSettings.id)
        .with_for_update(skip_locked=True)
    )
    return list(rows)
