"""T-67: сводка для руководителя — охват, расписание, отправка, журнал (docs/design/README.md §6.2).

Выпуск собирается теми же сервисами, что панель, поэтому проверяется не арифметика статусов, а
то, что принадлежит этой задаче: охват выпуска (район считает только свои школы, область — все),
выбор рассылки по дню недели и часу в Asia/Almaty, запись каждой попытки в ``notification_log``
и право на раздел — у чужого района его нет.

Ни один тест не ходит в сеть: в окружении тестов нет ни SMTP, ни бота Telegram — это и есть
случай, который журнал обязан объяснить, а не скрыть (ТЗ п. 18). Отправители подменены на весь
модуль, чтобы попытка открыть сокет была ошибкой теста, а не медленным тестом.
"""

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import DigestSettings, Notification, NotificationLog
from app.services.digest import build_digest
from app.services.digest_admin import due_digests
from app.services.notifications import CHANNEL_OFF
from tests.factories import bearer, create_user
from tests.test_admin_incident_rules import ok, problem
from tests.test_overview import WORKDAY, two_districts

DIGESTS = "/api/admin/digests"

# Пятница 14:00 Asia/Almaty — момент, в который живут данные ``two_districts``.
WEEKDAY = WORKDAY.isoweekday()
HOUR = WORKDAY.hour

# Адрес и чат теста: оба выдуманы, ни то ни другое не секрет (AGENTS.md §2.7).
RECIPIENT = "rukovoditel@example.kz"
CHAT_ID = "100500"


def no_network(*args: Any, **kwargs: Any) -> None:
    """Отправитель канала, который тест не просил: сокет здесь — ошибка, а не медленный тест."""
    raise AssertionError("тест не ходит в сеть: канал должен быть подменён")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Ни один канал не настроен и ни один не может выйти в сеть."""
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr("app.services.digest_admin.send_telegram", no_network)
    monkeypatch.setattr("app.services.digest_admin.send_email", no_network)
    return settings


async def a_mailing(
    session: AsyncSession, *, region_id: int | None = None, telegram: str | None = CHAT_ID
) -> DigestSettings:
    """Рассылка по охвату, назначенная на пятницу 14:00 — на момент данных теста."""
    mailing = DigestSettings(
        scope="oblast" if region_id is None else "region",
        region_id=region_id,
        weekday=WEEKDAY,
        hour=HOUR,
        recipients=[RECIPIENT],
        telegram_chat_id=telegram,
    )
    session.add(mailing)
    await session.flush()
    await session.refresh(mailing)
    return mailing


async def journal(session: AsyncSession) -> list[tuple[Any, ...]]:
    """Журнал доставок сводок: канал, результат, адресат, причина."""
    rows = await session.execute(
        select(
            NotificationLog.channel,
            NotificationLog.result,
            NotificationLog.target,
            NotificationLog.error,
        )
        .join(Notification, Notification.id == NotificationLog.notification_id)
        .where(Notification.kind == "digest_sent")
        .order_by(NotificationLog.id)
    )
    return [tuple(row) for row in rows]


async def test_a_district_digest_counts_only_its_own_schools(session: AsyncSession) -> None:
    school_a, school_b = await two_districts(session)

    district = await build_digest(session, region_id=school_a.region_id, now=WORKDAY)
    oblast = await build_digest(session, region_id=None, now=WORKDAY)

    assert district.summary.schools_count == 1
    assert oblast.summary.schools_count == 2
    # Школа другого района не попадает ни в числа, ни в «Худшие школы недели».
    assert all(row.school_name != school_b.full_name for row in district.worst)
    assert district.title != oblast.title


async def test_a_mailing_is_picked_at_its_weekday_and_hour(session: AsyncSession) -> None:
    await two_districts(session)
    mailing = await a_mailing(session)

    due = await due_digests(session, now=WORKDAY)
    later = await due_digests(session, now=WORKDAY + timedelta(hours=1))
    earlier = await due_digests(session, now=WORKDAY - timedelta(hours=1))

    assert [row.id for row in due] == [mailing.id]
    assert later == []
    assert earlier == []


async def test_a_mailing_is_not_picked_twice_in_one_window(session: AsyncSession) -> None:
    await two_districts(session)
    mailing = await a_mailing(session)
    mailing.last_sent_at = WORKDAY - timedelta(minutes=5)
    await session.flush()

    assert await due_digests(session, now=WORKDAY) == []


async def test_send_now_journals_every_channel_and_stamps_the_mailing(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    mailing = await a_mailing(session)
    oblast = bearer(await create_user(session, "oblast"))

    body = ok(await api_client.post(f"{DIGESTS}/{mailing.id}/send-now", headers=oblast))

    # По строке на канал: письмо получателю и сообщение в чат.
    assert [(item["channel"], item["result"]) for item in body["deliveries"]] == [
        ("email", "skipped"),
        ("telegram", "skipped"),
    ]
    assert await journal(session) == [
        ("email", "skipped", RECIPIENT, CHANNEL_OFF),
        ("telegram", "skipped", CHAT_ID, CHANNEL_OFF),
    ]
    await session.refresh(mailing)
    assert mailing.last_sent_at is not None


async def test_without_smtp_the_letter_is_recorded_as_not_sent(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    mailing = await a_mailing(session, telegram=None)
    oblast = bearer(await create_user(session, "oblast"))

    body = ok(await api_client.post(f"{DIGESTS}/{mailing.id}/send-now", headers=oblast))

    # Установка без SMTP — нормальная установка: не ошибка запроса, а skipped с причиной.
    assert body["deliveries"] == [
        {"channel": "email", "result": "skipped", "target": RECIPIENT, "error": CHANNEL_OFF}
    ]
    assert await journal(session) == [("email", "skipped", RECIPIENT, CHANNEL_OFF)]


async def test_preview_is_the_same_pdf_the_mailing_sends(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    mailing = await a_mailing(session)
    oblast = bearer(await create_user(session, "oblast"))

    response = await api_client.get(f"{DIGESTS}/{mailing.id}/preview", headers=oblast)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_a_district_user_neither_sees_nor_sends_a_mailing(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    mailing = await a_mailing(session, region_id=school_b.region_id)
    stranger = bearer(await create_user(session, "district", region_id=school_a.region_id))

    # Раздел рассылок — администрирование: у роли Район/город нет права settings:manage (ADR-008).
    problem(await api_client.get(DIGESTS, headers=stranger), 403, "forbidden")
    problem(
        await api_client.post(f"{DIGESTS}/{mailing.id}/send-now", headers=stranger),
        403,
        "forbidden",
    )
    problem(
        await api_client.get(f"{DIGESTS}/{mailing.id}/preview", headers=stranger), 403, "forbidden"
    )


async def test_the_list_and_the_crud_of_the_administration(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    admin = bearer(await create_user(session, "admin"))

    created = ok(
        await api_client.post(
            DIGESTS,
            headers=admin,
            json={
                "scope": "region",
                "region_id": school_a.region_id,
                "weekday": WEEKDAY,
                "hour": HOUR,
                "recipients": [RECIPIENT],
            },
        ),
        201,
    )
    listed = ok(await api_client.get(DIGESTS, headers=admin))
    changed = ok(
        await api_client.patch(
            f"{DIGESTS}/{created['id']}", headers=admin, json={"is_active": False}
        )
    )
    removed = await api_client.delete(f"{DIGESTS}/{created['id']}", headers=admin)

    assert created["scope"] == "region"
    assert created["region_id"] == school_a.region_id
    assert created["last_sent_at"] is None
    assert [item["id"] for item in listed["items"]] == [created["id"]]
    assert changed["is_active"] is False
    assert removed.status_code == 204
    assert await session.scalar(select(DigestSettings.id)) is None


async def test_a_mailing_without_a_channel_is_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    admin = bearer(await create_user(session, "admin"))

    problem(
        await api_client.post(
            DIGESTS,
            headers=admin,
            json={"scope": "oblast", "weekday": WEEKDAY, "hour": HOUR, "recipients": []},
        ),
        422,
        "validation_error",
    )
