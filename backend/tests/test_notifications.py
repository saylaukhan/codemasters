"""T-42: notifications of an incident — recipients, three channels, the journal (ТЗ п. 18).

Who hears about an incident is decided by the scope of ADR-008 and by nothing else: Область and
Администратор always, Район/город only in his own region, Школа only in her own school,
Провайдер only on his own lines. The headline of the task is the other half of that sentence —
a user of another district is not notified at all — so it is proved here on a whole oblast of
two districts, each with its own school and its own provider.

Everything that leaves the server is written down. The test environment configures neither
Telegram nor SMTP, which is exactly the case the journal has to explain instead of hide: both
channels are logged as «skipped» with a reason while the panel row is logged as sent. A send
that throws is logged as «failed» with its error and does not take the other channels with it.
No test here touches the network: the two senders are replaced for the whole module and a test
that wants a channel puts its own in.

The reading side goes through the API under RLS as ``vko_panel``, so the bell of one person also
proves the policy of the migration of T-42: he sees his own notifications and no one else's.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Incident, Line, Notification, NotificationLog, School, User
from app.services.notifications import CHANNEL_OFF, NO_ADDRESS, notify_incident
from app.workers.tasks.incidents import notify
from tests.factories import bearer, create_school, create_settings, create_user
from tests.test_admin_incident_rules import ok
from tests.test_incident_detection import FINE, NOW, SLOW, an_agent
from tests.test_incidents import an_incident

NOTIFICATIONS = "/api/notifications"
# Violations in a row the Download rule of the migration needs to open an incident (T-40).
VIOLATIONS = 3
# Grounds of an incident of Download, as ``METRIC_TITLES`` words them.
SLOW_DOWNLOAD = "Скорость загрузки ниже порога"

# A bot token and a chat of the test: both are made up, neither is a secret (AGENTS.md §2.7).
BOT_TOKEN = "test-bot-token"
CHAT_ID = "100500"
REFUSED = "Telegram ответил 502"


def no_network(*args: Any, **kwargs: Any) -> None:
    """Sender of a channel no test asked for: a socket here is a bug, not a slow test."""
    raise AssertionError("тест не ходит в сеть: канал должен быть подменён")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """No channel is configured and no channel may reach the network.

    The server of the tests has neither ``TELEGRAM_BOT_TOKEN`` nor ``SMTP_HOST``, the state the
    journal has to say out loud. A test that wants a channel turns it on and replaces its
    sender itself.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr("app.services.notifications.send_telegram", no_network)
    monkeypatch.setattr("app.services.notifications.send_email", no_network)
    return settings


@dataclass
class Oblast:
    """An incident of the school of district A and the nine people around it."""

    incident: Incident
    school_name: str
    # Everyone the incident is visible to (ADR-008).
    admin: User
    oblast: User
    district: User
    school: User
    provider: User
    # Everyone it is not: the other district with its own school and provider, and an account
    # of the oblast that was blocked without deleting it (ТЗ п. 16).
    other_district: User
    other_school: User
    other_provider: User
    blocked: User

    @property
    def sees(self) -> set[int]:
        return {self.admin.id, self.oblast.id, self.district.id, self.school.id, self.provider.id}


async def an_oblast(session: AsyncSession, client: AsyncClient) -> Oblast:
    """Two districts, a school and a provider in each, and an incident of the first school —
    opened by the detection of T-40 and notified about the way its task does it."""
    await create_settings(session)
    agent = await an_agent(session, client, "VKO-N-001")
    mine = await session.get_one(School, agent.line.school_id)
    other = await create_school(session, school_code="VKO-N-002")
    other_line = (await session.scalars(select(Line).where(Line.school_id == other.id))).one()

    everyone = {
        "admin": await create_user(session, "admin"),
        "oblast": await create_user(session, "oblast"),
        "district": await create_user(session, "district", region_id=mine.region_id),
        "school": await create_user(session, "school", school_id=mine.id),
        "provider": await create_user(session, "provider", provider_id=agent.line.provider_id),
        "other_district": await create_user(
            session, "district", email="district-b@example.kz", region_id=other.region_id
        ),
        "other_school": await create_user(
            session, "school", email="school-b@example.kz", school_id=other.id
        ),
        "other_provider": await create_user(
            session, "provider", email="provider-b@example.kz", provider_id=other_line.provider_id
        ),
        "blocked": await create_user(session, "oblast", email="uvolen@example.kz", is_active=False),
    }

    for _ in range(VIOLATIONS):
        detection = await agent.measure(SLOW)
    [incident_id] = detection.opened
    await notify(session, detection, NOW)
    incident = await session.get_one(Incident, incident_id)
    return Oblast(incident=incident, school_name=mine.full_name, **everyone)


async def notifications_of(session: AsyncSession, incident_id: int) -> list[Notification]:
    """Notifications the incident produced, oldest first."""
    return list(
        await session.scalars(
            select(Notification)
            .where(Notification.incident_id == incident_id)
            .order_by(Notification.id)
        )
    )


async def journal(session: AsyncSession, notification_id: int) -> list[tuple[Any, ...]]:
    """Every delivery attempt of one notification, in the order it was attempted."""
    rows = await session.execute(
        select(
            NotificationLog.channel,
            NotificationLog.result,
            NotificationLog.target,
            NotificationLog.error,
        )
        .where(NotificationLog.notification_id == notification_id)
        .order_by(NotificationLog.id)
    )
    return [tuple(row) for row in rows]


async def test_an_opened_incident_notifies_everyone_his_scope_lets_see_it(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    town = await an_oblast(session, api_client)

    rows = await notifications_of(session, town.incident.id)

    # One row per person and not one more: nobody is notified twice about the same incident.
    assert [row.user_id for row in rows] == sorted(town.sees)
    assert {row.kind for row in rows} == {"incident_opened"}
    assert {row.title for row in rows} == {f"Новый инцидент {town.incident.number}"}
    assert {row.body for row in rows} == {f"{town.school_name} · {SLOW_DOWNLOAD}"}
    assert {row.read_at for row in rows} == {None}


async def test_a_user_of_another_district_school_or_provider_is_not_notified(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    town = await an_oblast(session, api_client)

    notified = {row.user_id for row in await notifications_of(session, town.incident.id)}

    assert town.other_district.id not in notified, "район другой школы"
    assert town.other_school.id not in notified, "другая школа"
    assert town.other_provider.id not in notified, "провайдер другой линии"
    assert town.blocked.id not in notified, "заблокированная учётная запись"
    # And the bell of the stranger is empty, not merely unwritten: the endpoint answers him too.
    page = ok(await api_client.get(NOTIFICATIONS, headers=bearer(town.other_district)))
    assert (page["items"], page["total"]) == ([], 0)


async def test_every_channel_is_journalled_and_an_unconfigured_one_says_why(
    session: AsyncSession,
) -> None:
    school = await create_school(session, school_code="VKO-N-010")
    incident = await an_incident(session, school)
    await create_user(session, "admin")

    [notification_id] = await notify_incident(session, incident.id, "incident_opened", now=NOW)

    # The panel is the row itself and is always delivered; the two channels of the network are
    # not configured on this server and the journal says so instead of staying silent.
    assert await journal(session, notification_id) == [
        ("panel", "sent", "панель", None),
        ("telegram", "skipped", None, CHANNEL_OFF),
        ("email", "skipped", None, CHANNEL_OFF),
    ]


async def test_a_telegram_send_that_throws_is_journalled_as_failed_with_its_error(
    session: AsyncSession, offline: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(token: str, chat_id: str, text: str) -> None:
        raise RuntimeError(REFUSED)

    monkeypatch.setattr(offline, "telegram_bot_token", BOT_TOKEN)
    monkeypatch.setattr("app.services.notifications.send_telegram", refused)
    school = await create_school(session, school_code="VKO-N-011")
    incident = await an_incident(session, school)
    admin = await create_user(session, "admin")
    admin.telegram_chat_id = CHAT_ID
    oblast = await create_user(session, "oblast")  # the same bot, no chat of his own
    await session.flush()

    await notify_incident(session, incident.id, "incident_opened", now=NOW)

    rows = {row.user_id: row.id for row in await notifications_of(session, incident.id)}
    # The send failed, the notification did not: the panel row is there and says it was sent.
    assert await journal(session, rows[admin.id]) == [
        ("panel", "sent", "панель", None),
        ("telegram", "failed", CHAT_ID, REFUSED),
        ("email", "skipped", None, CHANNEL_OFF),
    ]
    assert await journal(session, rows[oblast.id]) == [
        ("panel", "sent", "панель", None),
        ("telegram", "skipped", None, NO_ADDRESS),
        ("email", "skipped", None, CHANNEL_OFF),
    ]


async def two_bells(session: AsyncSession) -> tuple[Incident, User, User]:
    """One incident and the two people notified about it: the oblast and the district of that
    school. Both may read it back, so what each of them sees is a matter of his own rows."""
    school = await create_school(session, school_code="VKO-N-020")
    incident = await an_incident(session, school)
    oblast = await create_user(session, "oblast")
    district = await create_user(session, "district", region_id=school.region_id)
    await notify_incident(session, incident.id, "incident_opened", now=NOW)
    return incident, oblast, district


async def test_the_bell_lists_the_notifications_of_the_caller_and_of_no_one_else(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    incident, oblast, district = await two_bells(session)
    rows = {row.user_id: row.id for row in await notifications_of(session, incident.id)}
    assert set(rows) == {oblast.id, district.id}

    for user in (oblast, district):
        page = ok(await api_client.get(NOTIFICATIONS, headers=bearer(user)))

        assert page["total"] == 1
        [item] = page["items"]
        assert item["id"] == rows[user.id], "уведомление другого пользователя"
        assert item["kind"] == "incident_opened"
        assert item["title"] == f"Новый инцидент {incident.number}"
        assert (item["incident_id"], item["incident_number"]) == (incident.id, incident.number)
        assert (item["incident_status"], item["school_name"]) == ("new", "Школа VKO-N-020")
        assert item["read_at"] is None


async def test_the_counter_and_read_all_are_about_the_caller_alone(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, oblast, district = await two_bells(session)
    his, hers = bearer(oblast), bearer(district)

    async def unread(headers: dict[str, str]) -> int:
        counter = ok(await api_client.get(f"{NOTIFICATIONS}/unread-count", headers=headers))
        return int(counter["unread"])

    async def unread_items(headers: dict[str, str]) -> list[dict[str, Any]]:
        params = {"unread_only": True}
        page = ok(await api_client.get(NOTIFICATIONS, params=params, headers=headers))
        assert page["total"] == len(page["items"])
        items: list[dict[str, Any]] = page["items"]
        return items

    assert (await unread(his), await unread(hers)) == (1, 1)
    assert len(await unread_items(his)) == 1

    response = await api_client.post(f"{NOTIFICATIONS}/read-all", headers=his)

    assert response.status_code == 204, response.text
    # «Отметить все как прочитанные» of one person leaves the bell of the other one ringing.
    assert (await unread(his), await unread(hers)) == (0, 1)
    assert await unread_items(his) == []
    [read] = ok(await api_client.get(NOTIFICATIONS, headers=his))["items"]
    assert read["read_at"] is not None
    [unread_of_hers] = ok(await api_client.get(NOTIFICATIONS, headers=hers))["items"]
    assert unread_of_hers["read_at"] is None


async def test_measurements_back_to_normal_notify_that_the_incident_is_restored(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client, "VKO-N-003")
    await create_user(session, "oblast")
    for _ in range(VIOLATIONS):
        opened = await agent.measure(SLOW)
    await notify(session, opened, NOW)
    [incident_id] = opened.opened

    await agent.measure(FINE)  # one norm is not a recovery yet (hysteresis, T-40)
    restored = await agent.measure(FINE)
    await notify(session, restored, NOW)

    assert restored.restored == [incident_id]
    incident = await session.get_one(Incident, incident_id)
    first, second = await notifications_of(session, incident_id)
    assert (first.kind, second.kind) == ("incident_opened", "incident_restored")
    assert second.title == f"Показатели восстановлены {incident.number}"
    assert second.body == f"Школа VKO-N-003 · показатели в норме · {SLOW_DOWNLOAD}"


async def test_a_status_change_by_a_person_is_handed_over_and_notifies(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    queued: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "app.api.incidents.enqueue_incident_notification",
        lambda incident_id, kind: queued.append((incident_id, kind)),
    )
    school = await create_school(session, school_code="VKO-N-030")
    incident = await an_incident(session, school)
    district = await create_user(session, "district", region_id=school.region_id)

    response = await api_client.post(
        f"/api/incidents/{incident.id}/status",
        json={"status": "in_progress", "comment": "Выехал инженер"},
        headers=bearer(district),
    )

    # The endpoint only queues the notification; the worker is what actually sends it.
    assert ok(response)["status"] == "in_progress"
    assert queued == [(incident.id, "incident_status_changed")]
    assert await notifications_of(session, incident.id) == []

    await notify_incident(session, incident.id, "incident_status_changed", now=NOW)

    [row] = await notifications_of(session, incident.id)
    assert (row.user_id, row.kind) == (district.id, "incident_status_changed")
    assert row.title == f"Инцидент изменён {incident.number}"
    assert row.body == f"Школа VKO-N-030 · статус «В работе» · {SLOW_DOWNLOAD}"
    assert await journal(session, row.id) == [
        ("panel", "sent", "панель", None),
        ("telegram", "skipped", None, CHANNEL_OFF),
        ("email", "skipped", None, CHANNEL_OFF),
    ]
