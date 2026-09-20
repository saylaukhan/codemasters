"""T-47: the draft of an appeal — facts without personal data, the prompt, the fallback.

The rule of ADR-011 is what these tests are for: the model is given School ID, the contract,
the period, the aggregates, the thresholds and an excerpt of the measurements, and never the
name, the position, the phone or the e-mail of the responsible person — those appear in the
answer afterwards. The model itself is a fake provider, so nothing here goes to the network:
a socket in this file is a bug and not a slow test.

The other half is what the editor of T-47 must always get: an installation without a model and
a model that does not answer are a 200 with ``ai_generated=false`` and a template, not an error
across the whole screen; a line of another school, an unknown id and a school outside the
user's scope are a 422 on the field of the request (ADR-008).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import Incident, Line, Measurement, Outage, Provider, School, SchoolContact
from app.services.llm import NO_KEY_DETAIL, UNAVAILABLE
from app.services.llm.base import LLMProvider, not_configured
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)
from tests.test_admin_incident_rules import ok, problem

DRAFT = "/api/appeals/draft"

SCHOOL_CODE = "VKO-UK-047"
LINE_IDENTIFIER = "L-77-014"
CONTRACT_NUMBER = "ДГ-2026-77"
PROVIDER_EMAIL = "appeals@provider.example.kz"

# Personal data of ТЗ п. 15: made up for the test, and never a word of it in the prompt.
CONTACT = {
    "full_name": "Иванова Айгуль Бахытовна",
    "position": "Заместитель директора",
    "phone": "+7 700 111 22 33",
    "email": "aigul.ivanova@example.kz",
}

ANSWER = "Уважаемые коллеги! Просим устранить несоответствие скорости по договору."

# Thresholds the measurements of the period were judged by (T-18, ADR-004).
SNAPSHOT: dict[str, Any] = {
    "profile_id": 1,
    "profile_scope": "global",
    "download_min_mbps": 20.0,
    "upload_min_mbps": 20.0,
    "ping_max_ms": 100.0,
    "jitter_max_ms": 30.0,
    "packet_loss_max_pct": 2.0,
    "unstable_deviation_pct": 30.0,
    "contract_down_mbps": 100.0,
    "contract_up_mbps": 50.0,
    "rates_line": True,
    "breaches": [],
}

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
OUTAGE = timedelta(minutes=30)


class FakeProvider(LLMProvider):
    """The model of the test: it answers a letter and remembers what it was asked (T-46)."""

    name = "fake"

    def __init__(self, answer: str = ANSWER, error: ApiError | None = None) -> None:
        self.answer = answer
        self.error = error
        self.prompt = ""
        self.system: str | None = None

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.prompt, self.system = prompt, system
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test of the draft asks the network: the transport of the adapter is not there."""

    def no_network(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("тест не ходит в сеть: модель должна быть подменена")

    monkeypatch.setattr("app.services.llm.base.request_json", no_network)


def model(monkeypatch: pytest.MonkeyPatch, provider: LLMProvider) -> None:
    """Put ``provider`` in the place the draft takes the model from (``get_provider``)."""
    monkeypatch.setattr("app.services.appeals.draft.get_provider", lambda *args: provider)


def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installation without a model: ``get_provider`` answers 503 as it does without a key."""

    def raise_not_configured(*args: Any) -> LLMProvider:
        raise not_configured(NO_KEY_DETAIL)

    monkeypatch.setattr("app.services.appeals.draft.get_provider", raise_not_configured)


def fields(response: Response) -> list[str]:
    return [error["field"] for error in problem(response, 422, "validation_error")["errors"]]


async def appealed_school(
    session: AsyncSession, *, code: str = SCHOOL_CODE
) -> tuple[School, Line, dict[str, str]]:
    """School with a contract of 100/50 Mbit/s, a responsible person, three measurements below
    the thresholds and one outage of half an hour; the third item is the period of the request.

    The period lies whole in the past, so nothing in it is cut by the moment of the request.
    """
    now = datetime.now(UTC)
    period_from, period_to = now - 7 * DAY, now - HOUR
    school = await create_school(session, school_code=code)
    device, _ = await register_device(
        session, await primary_point(session, school), device_uid=code
    )
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    line.line_identifier = LINE_IDENTIFIER
    line.contract_number = CONTRACT_NUMBER
    line.contract_date = date(2026, 1, 15)
    line.contract_down_mbps = 100
    line.contract_up_mbps = 50
    provider = await session.get_one(Provider, line.provider_id)
    provider.appeals_email = PROVIDER_EMAIL
    session.add(SchoolContact(school_id=school.id, **CONTACT))
    for hours, download, upload in [(48, 5.0, 3.0), (36, 7.0, 4.0), (24, 9.0, 5.0)]:
        session.add(
            Measurement(
                measurement_uuid=uuid.uuid4(),
                measured_at=period_to - hours * HOUR,
                device_id=device.id,
                line_id=line.id,
                connection_status="online",
                iface_type="ethernet",
                download_mbps=download,
                upload_mbps=upload,
                ping_ms=150.0,
                thresholds_snapshot=SNAPSHOT,
                quality_status="critical",
            )
        )
    session.add(
        Outage(
            device_id=device.id,
            line_id=line.id,
            started_at=period_from + DAY,
            ended_at=period_from + DAY + OUTAGE,
        )
    )
    await session.flush()
    return (
        school,
        line,
        {
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
        },
    )


async def an_incident(session: AsyncSession, school: School, line: Line) -> Incident:
    """Incident of the line, as the detection of T-40 opens it."""
    incident = Incident(
        number="INC-2026-000123",
        status="new",
        line_id=line.id,
        school_id=school.id,
        provider_id=line.provider_id,
        basis_metrics=[{"metric": "download_mbps", "value": 5.0, "threshold": 20.0}],
        started_at=datetime.now(UTC) - 2 * DAY,
    )
    session.add(incident)
    await session.flush()
    return incident


async def test_the_prompt_carries_the_facts_and_no_personal_data(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The main rule of ADR-011: facts to the model, contacts never (ТЗ п. 12, п. 15)."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    provider = FakeProvider()
    model(monkeypatch, provider)
    admin = bearer(await create_user(session, "admin"))

    body = ok(
        await api_client.post(
            DRAFT, json={"school_id": school.id, "line_id": line.id} | period, headers=admin
        )
    )

    prompt = provider.prompt
    assert SCHOOL_CODE in prompt
    assert CONTRACT_NUMBER in prompt
    assert LINE_IDENTIFIER in prompt
    # The fact of the period against the threshold and against the contract (plan.md §8).
    assert "среднее 7,0" in prompt
    assert "порог не ниже 20,0" in prompt
    assert "по договору не ниже 100,0" in prompt
    assert "Замеров за период: 3, из них с нарушением: 3" in prompt
    assert "Простоев: 1" in prompt
    for personal in CONTACT.values():
        assert personal not in prompt
        assert personal not in (provider.system or "")

    context = body["context"]
    assert context["school_code"] == SCHOOL_CODE
    assert (context["measurements_count"], context["problem_count"]) == (3, 3)
    assert context["download_mbps"] == {"avg": 7.0, "min": 5.0, "max": 9.0}
    assert context["jitter_ms"] is None
    assert context["thresholds"]["download_min_mbps"] == 20.0
    assert (context["outages_count"], context["outages_duration_s"]) == (1, OUTAGE.seconds)
    assert body["recipient_email"] == PROVIDER_EMAIL
    assert SCHOOL_CODE in body["subject"]


async def test_the_contacts_are_put_into_the_text_after_the_generation(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the model wrote, signed by the responsible person of the school (ТЗ п. 15)."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    model(monkeypatch, FakeProvider())
    admin = bearer(await create_user(session, "admin"))

    body = ok(
        await api_client.post(
            DRAFT, json={"school_id": school.id, "line_id": line.id} | period, headers=admin
        )
    )

    assert body["ai_generated"] is True
    assert ANSWER in body["text"]
    for personal in CONTACT.values():
        assert personal in body["text"]


async def test_a_draft_of_an_incident_carries_its_number(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The button of the incident card: the school and the line come from the incident."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    incident = await an_incident(session, school, line)
    provider = FakeProvider()
    model(monkeypatch, provider)
    admin = bearer(await create_user(session, "admin"))

    body = ok(
        await api_client.post(DRAFT, json={"incident_id": incident.id} | period, headers=admin)
    )

    assert body["context"]["incident_number"] == incident.number
    assert body["context"]["line_id"] == line.id
    assert incident.number in provider.prompt
    assert incident.number in body["subject"]


@pytest.mark.parametrize("broken", ["not_configured", "unavailable"])
async def test_a_silent_model_opens_the_editor_with_a_template(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    """503 of the adapter is not an error of the endpoint: a template with the facts (ADR-011)."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    if broken == "not_configured":
        no_model(monkeypatch)
    else:
        model(monkeypatch, FakeProvider(error=ApiError(503, UNAVAILABLE, "Модель недоступна")))
    admin = bearer(await create_user(session, "admin"))

    body = ok(
        await api_client.post(
            DRAFT, json={"school_id": school.id, "line_id": line.id} | period, headers=admin
        )
    )

    assert body["ai_generated"] is False
    assert SCHOOL_CODE in body["text"]
    assert CONTRACT_NUMBER in body["text"]
    assert "среднее 7,0" in body["text"]
    assert ANSWER not in body["text"]
    for personal in CONTACT.values():
        assert personal in body["text"]


async def test_an_unknown_target_and_a_line_of_another_school_are_422(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The target of a draft is checked before the model: the school comes from the line."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    _, other_line, _ = await appealed_school(session, code="VKO-UK-048")
    model(monkeypatch, FakeProvider())
    admin = bearer(await create_user(session, "admin"))

    for target, field in [
        ({"incident_id": 999_999}, "incident_id"),
        ({"school_id": 999_999, "line_id": line.id}, "school_id"),
        ({"school_id": school.id, "line_id": 999_999}, "line_id"),
        ({"school_id": school.id, "line_id": other_line.id}, "line_id"),
    ]:
        response = await api_client.post(DRAFT, json=target | period, headers=admin)

        assert fields(response) == [field], target


async def test_a_school_outside_the_scope_gives_no_draft(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stranger does not learn that the school and the incident exist (ADR-008, T-20)."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    incident = await an_incident(session, school, line)
    other = await create_school(session, school_code="VKO-UK-049")
    model(monkeypatch, FakeProvider())
    stranger = bearer(await create_user(session, "school", school_id=other.id))

    by_school = await api_client.post(
        DRAFT, json={"school_id": school.id, "line_id": line.id} | period, headers=stranger
    )
    by_incident = await api_client.post(
        DRAFT, json={"incident_id": incident.id} | period, headers=stranger
    )

    assert fields(by_school) == ["school_id"]
    assert fields(by_incident) == ["incident_id"]


async def test_a_role_without_the_right_does_not_create_appeals(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Провайдер reads appeals but does not write them (ТЗ п. 16, plan.md §9)."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    model(monkeypatch, FakeProvider())
    user = await create_user(session, "provider", provider_id=line.provider_id)

    response = await api_client.post(
        DRAFT, json={"school_id": school.id, "line_id": line.id} | period, headers=bearer(user)
    )

    assert "appeals:create" in problem(response, 403, "forbidden")["detail"]
