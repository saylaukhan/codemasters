"""Notifications of incidents: recipients, three channels, the journal (T-42; ТЗ п. 18; ADR-007).

An incident that is opened, restored or moved by a person notifies the people who may see it.
Recipients come from the scope of ADR-008 and nothing else: Область and Администратор get every
incident, Район/город only the incidents of the schools of his region, Школа only those of his
school, Провайдер only those of his own lines. A user of another district therefore never gets
a row — the same rule the RLS policies apply to the reading side, written here as one query.

Three channels leave the server: the ``notifications`` row itself is the panel channel, read by
the bell and by the stream of ``app/api/notifications.py``; Telegram and e-mail go out over the
network. Every attempt of every channel becomes a ``notification_log`` row, including the ones
that failed and the ones skipped because the channel is not configured — the journal has to
explain a silence, not hide it (ТЗ п. 18). A channel that throws never stops the others and
never rolls back the notification: the panel is the channel that must not be lost.

The writing side runs from Celery as the owner of the tables, outside any scope: it creates rows
for other people, which a panel session is not allowed to do. The reading side runs in the
request of one user and is limited to his own rows both by the query and by RLS.
"""

import asyncio
import json
import logging
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from typing import Any

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import PageParams
from app.models import Incident, Notification, NotificationLog, School, User, UserScope
from app.schemas.notifications import (
    NotificationListItem,
    NotificationListItemPage,
    NotificationUnreadCount,
)
from app.services.references import page_of

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
# A channel that hangs must not hold the worker: the beat run of the detection is every 5 minutes.
NETWORK_TIMEOUT_S = 10

# Russian titles of the notification, sentence case (ADR-013). The labels of the panel live in
# ``web/src/lib/labels.ts``; these are the stored text of the message itself.
KIND_TITLES = {
    "incident_opened": "Новый инцидент",
    "incident_status_changed": "Инцидент изменён",
    "incident_restored": "Показатели восстановлены",
}

# Metric of a basis, as ``IncidentMetric`` of ``app/schemas/statuses.py`` (ТЗ п. 18).
METRIC_TITLES = {
    "download_mbps": "Скорость загрузки ниже порога",
    "upload_mbps": "Скорость отдачи ниже порога",
    "ping_ms": "Ping выше порога",
    "jitter_ms": "Jitter выше порога",
    "packet_loss_pct": "Потери пакетов выше порога",
    "no_connection": "Нет соединения",
}

STATUS_TITLES = {
    "new": "Новый",
    "sent_to_provider": "Передан поставщику",
    "in_progress": "В работе",
    "awaiting_info": "Ожидает информации",
    "resolved": "Устранён",
    "closed": "Закрыт",
}

CHANNEL_OFF = "Канал не настроен на сервере"
NO_ADDRESS = "У пользователя нет адреса для этого канала"


@dataclass(frozen=True)
class Delivery:
    """One attempt: the channel, where it went, and what came of it."""

    channel: str
    result: str
    target: str | None = None
    error: str | None = None


def recipients_query(incident: Incident, region_id: int) -> Select[tuple[int]]:
    """Ids of the active users the incident is visible to (ADR-008).

    Область and Администратор see the whole oblast and have no ``user_scopes`` row; the other
    three roles are matched on the one id of their scope. The condition mirrors
    ``rls_school_ids`` and ``rls_line_ids`` of the migration of T-20, read from the other side:
    there a user asks which lines he sees, here a line asks which users see it.
    """
    return (
        select(User.id)
        .outerjoin(UserScope, UserScope.user_id == User.id)
        .where(
            User.is_active,
            or_(
                User.role.in_(("oblast", "admin")),
                (User.role == "district") & (UserScope.region_id == region_id),
                (User.role == "school") & (UserScope.school_id == incident.school_id),
                (User.role == "provider") & (UserScope.provider_id == incident.provider_id),
            ),
        )
        .order_by(User.id)
    )


def basis_text(basis_metrics: list[dict[str, Any]]) -> str:
    """Grounds of the incident in words: «Нет соединения», «Ping выше порога»."""
    titles = [
        METRIC_TITLES[metric["metric"]]
        for metric in basis_metrics
        if metric.get("metric") in METRIC_TITLES
    ]
    return ", ".join(titles) if titles else "Показатели качества"


def message(kind: str, incident: Incident, school_name: str) -> tuple[str, str]:
    """Title and body stored with the notification; they never change afterwards."""
    title = f"{KIND_TITLES[kind]} {incident.number}"
    grounds = basis_text(incident.basis_metrics)
    if kind == "incident_status_changed":
        body = f"{school_name} · статус «{STATUS_TITLES[incident.status]}» · {grounds}"
    elif kind == "incident_restored":
        body = f"{school_name} · показатели в норме · {grounds}"
    else:
        body = f"{school_name} · {grounds}"
    return title, body


async def create_notifications(
    session: AsyncSession, incident_id: int, kind: str, *, now: datetime
) -> list[int]:
    """Rows for everyone the incident is visible to; the ids of the new notifications.

    The caller commits. Runs as the owner of the tables (Celery): a panel session may not write
    a row that belongs to another person.
    """
    row = (
        await session.execute(
            select(Incident, School.full_name, School.region_id)
            .join(School, School.id == Incident.school_id)
            .where(Incident.id == incident_id)
        )
    ).first()
    if row is None:
        return []
    incident, school_name, region_id = row.Incident, row.full_name, row.region_id
    title, body = message(kind, incident, school_name)
    user_ids = list(await session.scalars(recipients_query(incident, region_id)))
    notifications = [
        Notification(
            user_id=user_id,
            incident_id=incident.id,
            kind=kind,
            title=title,
            body=body,
            created_at=now,
            updated_at=now,
        )
        for user_id in user_ids
    ]
    session.add_all(notifications)
    await session.flush()
    return [notification.id for notification in notifications]


def send_telegram(token: str, chat_id: str, text: str) -> None:
    """One message through the Telegram Bot API; raises on anything but a 200."""
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    request = urllib.request.Request(  # noqa: S310 — the scheme is ours, not user input
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_S) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"Telegram ответил {response.status}")


def send_email(settings: Settings, address: str, subject: str, text: str) -> None:
    """One letter over SMTP; raises on anything the server refuses."""
    letter = EmailMessage()
    letter["From"] = settings.smtp_from or settings.smtp_user
    letter["To"] = address
    letter["Subject"] = subject
    letter.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=NETWORK_TIMEOUT_S) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(letter)


async def deliver_telegram(settings: Settings, user: User, text: str) -> Delivery:
    if not settings.telegram_bot_token:
        return Delivery("telegram", "skipped", error=CHANNEL_OFF)
    if not user.telegram_chat_id:
        return Delivery("telegram", "skipped", error=NO_ADDRESS)
    try:
        await asyncio.to_thread(
            send_telegram, settings.telegram_bot_token, user.telegram_chat_id, text
        )
    except (OSError, urllib.error.URLError, RuntimeError) as error:
        return Delivery("telegram", "failed", user.telegram_chat_id, str(error))
    return Delivery("telegram", "sent", user.telegram_chat_id)


async def deliver_email(settings: Settings, user: User, subject: str, text: str) -> Delivery:
    if not settings.smtp_host:
        return Delivery("email", "skipped", error=CHANNEL_OFF)
    if not user.email:
        return Delivery("email", "skipped", error=NO_ADDRESS)
    try:
        await asyncio.to_thread(send_email, settings, user.email, subject, text)
    except (OSError, smtplib.SMTPException) as error:
        return Delivery("email", "failed", user.email, str(error))
    return Delivery("email", "sent", user.email)


async def deliver(session: AsyncSession, notification_ids: list[int], *, now: datetime) -> int:
    """Send every notification of ``notification_ids`` over Telegram and e-mail and write the
    journal of all three channels; how many rows the journal got. The caller commits.

    The panel channel is the notification row, already stored by ``create_notifications``, so it
    is written to the journal as sent. A channel that throws is written as failed and the next
    notification is still delivered.
    """
    if not notification_ids:
        return 0
    settings = get_settings()
    rows = (
        await session.execute(
            select(Notification, User)
            .join(User, User.id == Notification.user_id)
            .where(Notification.id.in_(notification_ids))
            .order_by(Notification.id)
        )
    ).all()
    logged = 0
    for row in rows:
        notification: Notification = row.Notification
        user: User = row.User
        text = f"{notification.title}\n{notification.body}"
        deliveries = [
            Delivery("panel", "sent", "панель"),
            await deliver_telegram(settings, user, text),
            await deliver_email(settings, user, notification.title, text),
        ]
        for item in deliveries:
            if item.result == "failed":
                logger.warning(
                    "notification %s: channel %s failed: %s",
                    notification.id,
                    item.channel,
                    item.error,
                )
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
            logged += 1
    await session.flush()
    return logged


async def notify_incident(
    session: AsyncSession, incident_id: int, kind: str, *, now: datetime
) -> list[int]:
    """Notify everyone the incident is visible to and journal every channel; the caller commits."""
    notification_ids = await create_notifications(session, incident_id, kind, now=now)
    await deliver(session, notification_ids, now=now)
    return notification_ids


# --- Reading side: the bell of one user (RLS limits it to his rows anyway) -------------------


def notification_rows(user_id: int) -> Select[Any]:
    """Notifications of one user with what the panel shows next to them."""
    return (
        select(
            Notification,
            Incident.number.label("incident_number"),
            Incident.status.label("incident_status"),
            Incident.school_id,
            School.full_name.label("school_name"),
        )
        .join(Incident, Incident.id == Notification.incident_id)
        .join(School, School.id == Incident.school_id)
        .where(Notification.user_id == user_id)
    )


def list_item(row: Any) -> NotificationListItem:
    notification: Notification = row.Notification
    return NotificationListItem.model_validate(
        {
            "id": notification.id,
            "kind": notification.kind,
            "title": notification.title,
            "body": notification.body,
            "incident_id": notification.incident_id,
            "incident_number": row.incident_number,
            "incident_status": row.incident_status,
            "school_id": row.school_id,
            "school_name": row.school_name,
            "read_at": notification.read_at,
            "created_at": notification.created_at,
        }
    )


async def notification_list(
    session: AsyncSession, user_id: int, *, unread_only: bool, params: PageParams
) -> NotificationListItemPage:
    """Page of the notifications of the user, newest first."""
    query = notification_rows(user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc())
    rows, total = await page_of(session, query, params)
    return NotificationListItemPage(
        items=[list_item(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def unread_count(session: AsyncSession, user_id: int) -> NotificationUnreadCount:
    """How many notifications of the user are unread: the counter on the bell."""
    total = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return NotificationUnreadCount(unread=total or 0)


async def mark_all_read(session: AsyncSession, user_id: int, *, now: datetime) -> int:
    """Mark every unread notification of the user as read; how many were marked."""
    marked = await session.scalars(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=now)
        .returning(Notification.id)
    )
    await session.commit()
    return len(marked.all())
