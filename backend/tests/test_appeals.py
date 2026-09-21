"""T-48: a sent appeal — the number, the letter, the PDF, the statuses and the history (ТЗ п. 17).

The rule the first tests are for is the one ADR-011 names: a draft costs nothing and is nothing,
a number is the mark of a sent letter. Asking for a draft twice must leave the table empty; one
«Отправить» must leave exactly one appeal with ``ОБР-<year>-<six digits>``, its PDF and the first
row of its history.

The second half is the cabinet of the provider (T-44, ADR-008): he moves the status of his own
appeal, every move is an ``appeal_events`` row, «Закрыт» is not his to put, and an appeal of
another provider's line is simply not there — 404, not 403. An installation without SMTP is a
normal installation: the appeal is stored and marked «не отправлено» with its PDF kept.

The last two are T-63: an appeal sent from the card of an incident in «Новый» hands the
incident over to the provider by itself, with a row of its history naming the appeal; an
incident a person already moved is not touched.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Appeal, AppealEvent, Line
from tests.factories import bearer, create_settings, create_user
from tests.test_admin_incident_rules import ok, problem
from tests.test_appeal_draft import PROVIDER_EMAIL, an_incident, appealed_school

APPEALS = "/api/appeals"
INCIDENTS = "/api/incidents"

SUBJECT = "Качество интернет-соединения: VKO-UK-047, период 01.09.2026 — 08.09.2026"
TEXT = "**Провайдер**\n\nУважаемые коллеги!\n\n- Замеров за период: 3\n\n---\n\nОтветственное лицо"
USER_COMMENT = "Просим ответить до конца недели."

SMTP_HOST = "smtp.example.kz"


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """No SMTP on the server of the tests and no way out to the network from here.

    A test that wants a letter turns the channel on and replaces the sender itself.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "")

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("тест не ходит в сеть: отправка письма должна быть подменена")

    monkeypatch.setattr("app.services.appeals.send.send_email", no_network)
    return settings


def letters(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> list[tuple[Any, ...]]:
    """Turn the e-mail channel on and remember every letter instead of sending it."""
    sent: list[tuple[Any, ...]] = []
    monkeypatch.setattr(settings, "smtp_host", SMTP_HOST)
    monkeypatch.setattr("app.services.appeals.send.send_email", lambda *args: sent.append(args))
    return sent


async def sent_appeal(
    session: AsyncSession, client: AsyncClient, headers: dict[str, str], **extra: Any
) -> dict[str, Any]:
    """School with a week of bad measurements and one appeal sent about its line."""
    school, line, period = await appealed_school(session, **extra)
    body = {"school_id": school.id, "line_id": line.id} | period
    return ok(
        await client.post(
            APPEALS,
            json=body | {"subject": SUBJECT, "text": TEXT, "user_comment": USER_COMMENT},
            headers=headers,
        ),
        201,
    )


async def appeals_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Appeal)) or 0


async def test_the_number_is_given_by_the_sending_and_not_by_the_draft(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ТЗ п. 17: a draft is not stored and has no number; «Отправить» gives both (ADR-011)."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    monkeypatch.setattr("app.services.appeals.draft.get_provider", lambda *args: _silent_provider())
    admin = bearer(await create_user(session, "admin"))
    target = {"school_id": school.id, "line_id": line.id} | period

    draft = ok(await api_client.post(f"{APPEALS}/draft", json=target, headers=admin))
    assert "number" not in draft
    assert await appeals_count(session) == 0

    appeal = ok(
        await api_client.post(
            APPEALS, json=target | {"subject": SUBJECT, "text": TEXT}, headers=admin
        ),
        201,
    )

    year = datetime.now(UTC).astimezone().year
    assert appeal["number"].startswith(f"ОБР-{year}-")
    assert len(appeal["number"].rsplit("-", 1)[1]) == 6
    assert appeal["status"] == "sent_to_provider"
    assert await appeals_count(session) == 1
    # The first row of the history is the sending itself (ТЗ п. 17).
    assert [(event["status"], event["comment"]) for event in appeal["events"]] == [
        ("sent_to_provider", None)
    ]
    assert appeal["context"]["school_code"] == "VKO-UK-047"


async def test_without_smtp_the_appeal_keeps_its_pdf_and_is_marked_not_sent(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """«Решения по умолчанию»: no SMTP is not an error — the PDF is stored and opens."""
    await create_settings(session)
    admin = bearer(await create_user(session, "admin"))

    appeal = await sent_appeal(session, api_client, admin)

    assert appeal["delivery_status"] == "not_sent"
    assert appeal["recipient_email"] == PROVIDER_EMAIL
    response = await api_client.get(f"{APPEALS}/{appeal['id']}/pdf", headers=admin)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.7")
    assert (
        appeal["number"] in response.headers["content-disposition"]
        or "UTF-8" in (response.headers["content-disposition"])
    )


async def test_the_letter_goes_to_the_provider_with_the_pdf_attached(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ТЗ п. 17: the letter goes to ``providers.appeals_email`` and carries the PDF."""
    await create_settings(session)
    settings = get_settings()
    sent = letters(monkeypatch, settings)
    admin = bearer(await create_user(session, "admin"))

    appeal = await sent_appeal(session, api_client, admin)

    assert appeal["delivery_status"] == "sent"
    assert len(sent) == 1
    _, address, subject, text, attachment = sent[0]
    assert address == PROVIDER_EMAIL
    assert subject == SUBJECT
    # The comment of the person travels next to the letter, not inside its text (ТЗ п. 17).
    assert text.startswith(TEXT)
    assert USER_COMMENT in text
    name, content = attachment
    assert name == f"{appeal['number']}.pdf"
    assert content.startswith(b"%PDF-1.7")


async def test_a_school_sends_an_appeal_about_its_own_line(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """ADR-008: «Создать обращение» is the school's right, and RLS lets it write its own row."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    user = bearer(await create_user(session, "school", school_id=school.id))

    appeal = ok(
        await api_client.post(
            APPEALS,
            json={"school_id": school.id, "line_id": line.id}
            | period
            | {"subject": SUBJECT, "text": TEXT},
            headers=user,
        ),
        201,
    )

    assert appeal["number"].startswith("ОБР-")
    listed = ok(await api_client.get(APPEALS, headers=user))
    assert [item["id"] for item in listed["items"]] == [appeal["id"]]


async def test_a_provider_moves_the_status_and_the_history_keeps_every_move(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """ТЗ п. 17, п. 19: the six statuses of an incident, every transition in ``appeal_events``."""
    await create_settings(session)
    admin = bearer(await create_user(session, "admin"))
    appeal = await sent_appeal(session, api_client, admin)
    line = await session.get_one(Line, appeal["context"]["line_id"])
    provider = bearer(await create_user(session, "provider", provider_id=line.provider_id))

    moved = ok(
        await api_client.patch(
            f"{APPEALS}/{appeal['id']}",
            json={"status": "in_progress", "comment": "Заявка принята"},
            headers=provider,
        )
    )
    commented = ok(
        await api_client.patch(
            f"{APPEALS}/{appeal['id']}", json={"comment": "Выехал инженер"}, headers=provider
        )
    )

    assert moved["status"] == "in_progress"
    assert commented["status"] == "in_progress"
    assert [(event["status"], event["comment"]) for event in commented["events"]] == [
        ("sent_to_provider", None),
        ("in_progress", "Заявка принята"),
        (None, "Выехал инженер"),
    ]
    assert {event["author_user_name"] for event in commented["events"]} == {
        "Пользователь admin",
        "Пользователь provider",
    }
    kinds = await session.scalars(
        select(AppealEvent.kind)
        .where(AppealEvent.appeal_id == appeal["id"])
        .order_by(AppealEvent.id)
    )
    assert list(kinds) == ["sent", "status_change", "comment"]


async def test_a_provider_may_not_close_an_appeal_and_may_not_skip_backwards(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """ADR-007: «Закрыт» is for the district and the oblast; the other moves follow T-41."""
    await create_settings(session)
    admin = bearer(await create_user(session, "admin"))
    appeal = await sent_appeal(session, api_client, admin)
    line = await session.get_one(Line, appeal["context"]["line_id"])
    provider = bearer(await create_user(session, "provider", provider_id=line.provider_id))
    path = f"{APPEALS}/{appeal['id']}"

    refused = await api_client.patch(path, json={"status": "closed"}, headers=provider)
    problem(refused, 403, "forbidden")
    ok(await api_client.patch(path, json={"status": "resolved"}, headers=provider))
    problem(
        await api_client.patch(path, json={"status": "sent_to_provider"}, headers=provider),
        409,
        "invalid_status_transition",
    )
    closed = ok(await api_client.patch(path, json={"status": "closed"}, headers=admin))
    assert closed["status"] == "closed"


async def test_a_stranger_does_not_see_an_appeal(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """ADR-008: an appeal of another provider's line is not there at all — 404, not 403."""
    await create_settings(session)
    admin = bearer(await create_user(session, "admin"))
    mine = await sent_appeal(session, api_client, admin)
    other = await sent_appeal(session, api_client, admin, code="VKO-UK-048")
    line = await session.get_one(Line, mine["context"]["line_id"])
    provider = bearer(await create_user(session, "provider", provider_id=line.provider_id))

    listed = ok(await api_client.get(APPEALS, headers=provider))
    assert [item["id"] for item in listed["items"]] == [mine["id"]]
    ok(await api_client.get(f"{APPEALS}/{mine['id']}", headers=provider))
    path = f"{APPEALS}/{other['id']}"
    for method, url, body in [
        ("GET", path, None),
        ("GET", f"{path}/pdf", None),
        ("PATCH", path, {"status": "in_progress"}),
    ]:
        response = await api_client.request(method, url, json=body, headers=provider)
        problem(response, 404, "not_found")


async def test_an_appeal_from_a_new_incident_hands_it_over_to_the_provider(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """T-63 (ADR-007): «Отправить» from the card of an incident in «Новый» is the handing over
    itself — the incident moves to «Передан поставщику» with a row of its history."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    incident = await an_incident(session, school, line)
    user = await create_user(session, "admin")
    admin = bearer(user)
    before = datetime.now(UTC)

    appeal = ok(
        await api_client.post(
            APPEALS,
            json={"incident_id": incident.id} | period | {"subject": SUBJECT, "text": TEXT},
            headers=admin,
        ),
        201,
    )

    assert appeal["context"]["incident_id"] == incident.id
    card = ok(await api_client.get(f"{INCIDENTS}/{incident.id}", headers=admin))
    assert card["status"] == "sent_to_provider"
    sent_at = datetime.fromisoformat(card["sent_to_provider_at"])
    assert before <= sent_at <= datetime.now(UTC)
    assert [
        (e["kind"], e["from_status"], e["to_status"], e["author_user_id"]) for e in card["events"]
    ] == [("status_change", "new", "sent_to_provider", user.id)]
    assert appeal["number"] in card["events"][0]["comment"]


async def test_an_appeal_leaves_an_incident_already_in_work_as_it_is(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """T-63: an incident a person already moved keeps its status and its history."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    incident = await an_incident(session, school, line)
    incident.status = "in_progress"
    await session.flush()
    admin = bearer(await create_user(session, "admin"))

    ok(
        await api_client.post(
            APPEALS,
            json={"incident_id": incident.id} | period | {"subject": SUBJECT, "text": TEXT},
            headers=admin,
        ),
        201,
    )

    card = ok(await api_client.get(f"{INCIDENTS}/{incident.id}", headers=admin))
    assert card["status"] == "in_progress"
    assert card["sent_to_provider_at"] is None
    assert card["events"] == []


def _silent_provider() -> Any:
    """The model of T-47 is not the subject here: the draft may answer with its template."""
    from app.services.llm import NO_KEY_DETAIL
    from app.services.llm.base import not_configured

    raise not_configured(NO_KEY_DETAIL)
