"""T-86: templates of the letters to providers — the admin panel, the filled letter, the draft.

The rule the first tests are for is ТЗ п. 20 read with ADR-011: the structure of the letter is
not a constant of the code but a template Область and Администратор edit, and the model writes
by the template filled with facts. The default template is the one a draft takes without a
choice, and there is always exactly one; a template is switched off, never deleted.

The second half is the draft itself: a claim is a claim in the subject, the prompt, the sent
appeal and its PDF; an unknown placeholder never reaches the table; a template that does not
exist or is switched off is a 422 on the field, as any other target of a draft (ADR-008).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppealTemplate, AuditLog, Provider
from app.schemas.appeal_templates import PLACEHOLDERS, unknown_placeholders
from app.schemas.appeals import AppealContext
from app.schemas.thresholds import ThresholdValues
from app.services.appeals.context import AppealFacts
from app.services.appeals.template import placeholder_values, render
from tests.factories import bearer, create_school, create_settings, create_user
from tests.test_admin_incident_rules import ok, problem
from tests.test_appeal_draft import (
    CONTRACT_NUMBER,
    DRAFT,
    LINE_IDENTIFIER,
    SCHOOL_CODE,
    FakeProvider,
    appealed_school,
    model,
    no_model,
)
from tests.test_appeals import APPEALS, SUBJECT, TEXT

TEMPLATES = "/api/admin/appeal-templates"

CLAIM = {
    "name": "Претензия с перерасчётом",
    "kind": "claim",
    "subject": "Претензия по договору {{contract_number}}: {{school_code}}",
    "body": "**{{provider_name}}**\n\nПо договору № {{contract_number}} от {{contract_date}} "
    "скорость не ниже {{contract_down_mbps}} Мбит/с.\n\n{{facts}}\n\n{{metrics}}\n\n"
    "Требуем перерасчёта за период {{period}}.",
    "ai_instructions": "Сошлись на пункт договора о штрафных санкциях.",
}


def facts_of(**overrides: Any) -> AppealFacts:
    """Facts of a letter built by hand: no database, no network."""
    period_from = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)
    context = AppealContext(
        incident_id=None,
        incident_number=None,
        school_id=1,
        school_code="VKO-UK-007",
        school_name="Школа № 7",
        line_id=2,
        line_identifier="L-7",
        provider_id=3,
        provider_name="ТОО «Связь»",
        contract_number="ДГ-7",
        contract_date=date(2026, 1, 15),
        contract_down_mbps=100.0,
        contract_up_mbps=50.0,
        period_from=period_from,
        period_to=period_from + timedelta(days=7),
        measurements_count=12,
        problem_count=9,
        download_mbps=None,
        upload_mbps=None,
        ping_ms=None,
        jitter_ms=None,
        packet_loss_pct=None,
        thresholds=ThresholdValues(
            download_min_mbps=20,
            upload_min_mbps=20,
            ping_max_ms=100,
            jitter_max_ms=30,
            packet_loss_max_pct=2,
        ),
        outages_count=2,
        outages_duration_s=5400,
        **overrides,
    )
    return AppealFacts(context=context, excerpt=[], recipient_email=None, timezone="Asia/Almaty")


async def templates_in_table(session: AsyncSession) -> list[tuple[str, str, bool, bool]]:
    rows = await session.execute(
        select(
            AppealTemplate.name,
            AppealTemplate.kind,
            AppealTemplate.is_default,
            AppealTemplate.is_active,
        ).order_by(AppealTemplate.id)
    )
    return [tuple(row) for row in rows]


def test_every_placeholder_has_a_value_and_the_letter_is_filled_with_them() -> None:
    """The vocabulary of the schema and the values of the service are one list."""
    values = placeholder_values(facts_of())

    assert set(values) == set(PLACEHOLDERS)
    letter = render(
        "{{school_name}} ({{ school_code }}), договор {{contract_number}} от {{contract_date}}, "
        "{{contract_down_mbps}}/{{contract_up_mbps}}, период {{period}}, простои "
        "{{outages_count}} на {{outages_duration}}; инцидент {{incident_number}}; {{unknown}}",
        values,
    )
    assert letter == (
        "Школа № 7 (VKO-UK-007), договор ДГ-7 от 15.01.2026, 100,0/50,0, период "
        "01.09.2026 08:00 — 08.09.2026 08:00, простои 2 на 1 ч 30 мин; инцидент —; "
        "{{unknown}}"
    )
    assert "School ID: VKO-UK-007" in values["facts"]
    assert "по договору не ниже 100,0" in values["metrics"]
    assert unknown_placeholders("{{school_name}} {{foo}} {{bar}} {{foo}}") == ["foo", "bar"]


async def test_the_default_templates_are_listed_the_default_first(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))

    page = ok(await api_client.get(TEMPLATES, headers=oblast))
    placeholders = ok(await api_client.get(f"{TEMPLATES}/placeholders", headers=oblast))

    assert [(item["name"], item["kind"], item["is_default"]) for item in page["items"]] == [
        ("Обращение поставщику", "appeal", True),
        ("Претензионное письмо", "claim", False),
    ]
    assert all(item["is_active"] for item in page["items"])
    assert (
        "{{school_name}}" in page["items"][0]["subject"]
        or "{{school_code}}" in (page["items"][0]["subject"])
    )
    assert [item["name"] for item in placeholders["items"]] == list(PLACEHOLDERS)


async def test_a_template_is_created_made_the_default_and_audited(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    admin = bearer(await create_user(session, "admin"))
    old_default = ok(await api_client.get(TEMPLATES, headers=admin))["items"][0]

    created = ok(await api_client.post(TEMPLATES, json=CLAIM, headers=admin), 201)
    promoted = ok(
        await api_client.patch(
            f"{TEMPLATES}/{created['id']}", json={"is_default": True}, headers=admin
        )
    )
    listed = ok(await api_client.get(TEMPLATES, headers=admin))

    assert created["kind"] == "claim" and created["is_default"] is False
    assert created["is_active"] is True
    assert promoted["is_default"] is True
    # The mark moved: the old default lost it and the new one leads the list.
    assert [(item["id"], item["is_default"]) for item in listed["items"]][0] == (
        created["id"],
        True,
    )
    assert sum(item["is_default"] for item in listed["items"]) == 1
    assert old_default["id"] in [item["id"] for item in listed["items"] if not item["is_default"]]
    records = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == "appeal_template")
        .order_by(AuditLog.id)
    )
    assert [tuple(row) for row in records] == [
        ("create", created["id"], None),
        ("update", created["id"], {"is_default": {"old": False, "new": True}}),
    ]


async def test_the_default_template_cannot_be_switched_off_or_demoted(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))
    default, claim = ok(await api_client.get(TEMPLATES, headers=oblast))["items"]

    problem(
        await api_client.patch(
            f"{TEMPLATES}/{default['id']}", json={"is_active": False}, headers=oblast
        ),
        409,
        "default_template_required",
    )
    problem(
        await api_client.patch(
            f"{TEMPLATES}/{default['id']}", json={"is_default": False}, headers=oblast
        ),
        409,
        "default_template_required",
    )
    # A switched-off template cannot be the default either.
    problem(
        await api_client.patch(
            f"{TEMPLATES}/{claim['id']}",
            json={"is_active": False, "is_default": True},
            headers=oblast,
        ),
        422,
        "validation_error",
    )
    switched_off = ok(
        await api_client.patch(
            f"{TEMPLATES}/{claim['id']}", json={"is_active": False}, headers=oblast
        )
    )
    problem(
        await api_client.patch(f"{TEMPLATES}/999999", json={"name": "x"}, headers=oblast),
        404,
        "not_found",
    )

    assert switched_off["is_active"] is False
    assert await templates_in_table(session) == [
        ("Обращение поставщику", "appeal", True, True),
        ("Претензионное письмо", "claim", False, False),
    ]


async def test_an_unknown_placeholder_is_rejected_on_its_field(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))
    claim_id = ok(await api_client.get(TEMPLATES, headers=oblast))["items"][1]["id"]

    created = problem(
        await api_client.post(
            TEMPLATES, json=CLAIM | {"body": "Уважаемые {{director_name}}!"}, headers=oblast
        ),
        422,
        "validation_error",
    )
    changed = problem(
        await api_client.patch(
            f"{TEMPLATES}/{claim_id}", json={"subject": "{{school}} {{phone}}"}, headers=oblast
        ),
        422,
        "validation_error",
    )

    assert [error["field"] for error in created["errors"]] == ["body"]
    assert "{{director_name}}" in created["errors"][0]["message"]
    assert [error["field"] for error in changed["errors"]] == ["subject"]
    assert "{{school}}, {{phone}}" in changed["errors"][0]["message"]
    assert len(await templates_in_table(session)) == 2


@pytest.mark.parametrize("role", ["school", "district", "provider", "oblast", "admin"])
async def test_only_oblast_and_administrator_manage_templates(
    session: AsyncSession, api_client: AsyncClient, role: str
) -> None:
    school = await create_school(session)
    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id.desc()).limit(1))
    scope = {
        "school": {"school_id": school.id},
        "district": {"region_id": school.region_id},
        "provider": {"provider_id": provider_id},
    }.get(role, {})
    user = bearer(await create_user(session, role, **scope))
    # The claim template is renamed, so the default one keeps its name for the check below.
    template_id = await session.scalar(
        select(AppealTemplate.id).where(AppealTemplate.kind == "claim").order_by(AppealTemplate.id)
    )

    responses = [
        await api_client.get(TEMPLATES, headers=user),
        await api_client.post(TEMPLATES, json=CLAIM, headers=user),
        await api_client.patch(f"{TEMPLATES}/{template_id}", json={"name": "x"}, headers=user),
    ]
    options = await api_client.get(f"{APPEALS}/templates", headers=user)

    if role in ("oblast", "admin"):
        assert [response.status_code for response in responses] == [200, 201, 200]
    else:
        for response in responses:
            problem(response, 403, "forbidden")
    # Whoever writes appeals chooses among the templates; the provider does not write them.
    if role == "provider":
        problem(options, 403, "forbidden")
    else:
        items = ok(options)["items"]
        assert items[0]["name"] == "Обращение поставщику" and items[0]["is_default"]
        assert {item["kind"] for item in items} == {"appeal", "claim"}


async def test_the_draft_of_a_claim_is_written_by_the_filled_claim_template(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ТЗ п. 17 with T-86: the model gets the filled template and its instructions; without
    the model the editor opens with the filled template itself."""
    await create_settings(session)
    school, line, period = await appealed_school(session)
    provider = FakeProvider()
    model(monkeypatch, provider)
    admin = bearer(await create_user(session, "admin"))
    claim = ok(await api_client.post(TEMPLATES, json=CLAIM, headers=admin), 201)
    target = {"school_id": school.id, "line_id": line.id} | period

    by_default = ok(await api_client.post(DRAFT, json=target, headers=admin))
    as_claim = ok(
        await api_client.post(DRAFT, json=target | {"template_id": claim["id"]}, headers=admin)
    )
    claim_prompt = provider.prompt
    no_model(monkeypatch)
    by_hand = ok(
        await api_client.post(DRAFT, json=target | {"template_id": claim["id"]}, headers=admin)
    )

    assert (by_default["kind"], by_default["template_name"]) == ("appeal", "Обращение поставщику")
    assert by_default["subject"].startswith(f"Качество интернет-соединения: {SCHOOL_CODE}, ")
    assert (as_claim["kind"], as_claim["template_id"]) == ("claim", claim["id"])
    assert as_claim["subject"] == f"Претензия по договору {CONTRACT_NUMBER}: {SCHOOL_CODE}"
    # The model was given the filled letter and the instructions of the template, not the marks.
    assert f"По договору № {CONTRACT_NUMBER} от 15.01.2026 скорость не ниже 100,0" in claim_prompt
    assert CLAIM["ai_instructions"] in claim_prompt
    assert "{{" not in claim_prompt
    assert LINE_IDENTIFIER in claim_prompt
    # Without the model the letter is the filled template, the facts already in it.
    assert by_hand["ai_generated"] is False
    assert "Требуем перерасчёта за период" in by_hand["text"]
    assert f"договору № {CONTRACT_NUMBER}" in by_hand["text"]
    assert "{{" not in by_hand["text"]


async def test_an_unknown_or_switched_off_template_is_422_on_its_field(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await create_settings(session)
    school, line, period = await appealed_school(session)
    model(monkeypatch, FakeProvider())
    admin = bearer(await create_user(session, "admin"))
    claim_id = ok(await api_client.get(TEMPLATES, headers=admin))["items"][1]["id"]
    ok(await api_client.patch(f"{TEMPLATES}/{claim_id}", json={"is_active": False}, headers=admin))
    target = {"school_id": school.id, "line_id": line.id} | period

    for template_id in (999_999, claim_id):
        body = problem(
            await api_client.post(DRAFT, json=target | {"template_id": template_id}, headers=admin),
            422,
            "validation_error",
        )
        assert [error["field"] for error in body["errors"]] == ["template_id"]
    # The switched-off template is not offered to the editor either.
    options = ok(await api_client.get(f"{APPEALS}/templates", headers=admin))
    assert [item["id"] for item in options["items"]] != [claim_id] and claim_id not in [
        item["id"] for item in options["items"]
    ]


async def test_a_sent_claim_keeps_its_kind_and_template(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, line, period = await appealed_school(session)
    admin = bearer(await create_user(session, "admin"))
    claim_id = ok(await api_client.get(TEMPLATES, headers=admin))["items"][1]["id"]

    appeal = ok(
        await api_client.post(
            APPEALS,
            json={"school_id": school.id, "line_id": line.id, "template_id": claim_id}
            | period
            | {"subject": SUBJECT, "text": TEXT},
            headers=admin,
        ),
        201,
    )
    listed = ok(await api_client.get(APPEALS, headers=admin))
    pdf = await api_client.get(f"{APPEALS}/{appeal['id']}/pdf", headers=admin)

    assert (appeal["kind"], appeal["template_id"]) == ("claim", claim_id)
    assert listed["items"][0]["kind"] == "claim"
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-1.7")
