"""T-44: the cabinet of a provider — his lines and their incidents (ТЗ п. 16, п. 19).

Demo scenario 5 of plan.md §15 read as a test: a provider signs in and sees only what he serves.
The two districts of ``test_overview``: school A is served by provider A, school B by provider B;
the user of the test is provider B. What he may not see is «не найдено», not «запрещено» — its
existence is not disclosed (ADR-008) — and what he may not do is a 403 of the role (ADR-007):
«Закрыт» is put by the district or the oblast, or by beat 24 hours after «Устранён».
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import ROLE_PERMISSIONS
from app.models import Incident, Line, Provider, School, SchoolContact
from tests.factories import bearer, create_user
from tests.test_admin_incident_rules import ok, problem
from tests.test_analytics import DAY
from tests.test_overview import WORKDAY, get, two_districts

STARTED = WORKDAY - timedelta(hours=2)
PHONE = "+7 701 000 00 00"

# Everything the administration of ТЗ п. 16 answers on: a provider gets 403 on each of them.
ADMIN_PATHS = [
    "/api/admin/users",
    "/api/admin/regions",
    "/api/admin/providers",
    "/api/admin/thresholds",
    "/api/admin/schedules",
    "/api/admin/incident-rules",
    "/api/admin/settings",
    "/api/admin/audit-log",
]


async def line_of(session: AsyncSession, school: School) -> Line:
    return (await session.scalars(select(Line).where(Line.school_id == school.id))).one()


async def an_incident(session: AsyncSession, school: School, number: str) -> Incident:
    """Incident of the main line of ``school``, as the detection of T-40 opens it."""
    line = await line_of(session, school)
    incident = Incident(
        number=number,
        status="new",
        line_id=line.id,
        school_id=school.id,
        provider_id=line.provider_id,
        basis_metrics=[{"metric": "download_mbps", "value": 5.0, "threshold": 20.0}],
        started_at=STARTED,
    )
    session.add(incident)
    await session.flush()
    return incident


async def a_contact(session: AsyncSession, school: School, name: str) -> SchoolContact:
    contact = SchoolContact(
        school_id=school.id, full_name=name, phone=PHONE, email=f"{school.school_code}@example.kz"
    )
    session.add(contact)
    await session.flush()
    return contact


async def change(
    client: AsyncClient, incident: Incident, status: str, headers: dict[str, str], comment: str
) -> Response:
    return await client.post(
        f"/api/incidents/{incident.id}/status",
        json={"status": status, "comment": comment},
        headers=headers,
    )


async def provider_of(session: AsyncSession, school: School) -> dict[str, str]:
    """Headers of a user of the provider that serves ``school``."""
    line = await line_of(session, school)
    return bearer(await create_user(session, "provider", provider_id=line.provider_id))


async def test_the_cabinet_holds_only_the_schools_incidents_and_numbers_of_its_lines(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    await an_incident(session, school_a, "INC-2026-000001")
    mine = await an_incident(session, school_b, "INC-2026-000002")
    await a_contact(session, school_a, "Директор A")
    await a_contact(session, school_b, "Директор B")
    provider = await provider_of(session, school_b)

    schools = await get(api_client, "/api/schools", provider)
    incidents = await get(api_client, "/api/incidents", provider)
    by_school = await get(api_client, "/api/analytics", provider, level="school", **DAY)
    by_provider = await get(api_client, "/api/analytics", provider, level="provider", **DAY)
    contacts = await get(api_client, f"/api/schools/{school_b.id}/contacts", provider)

    assert [item["school_code"] for item in schools["items"]] == ["VKO-B-001"]
    assert [item["number"] for item in incidents["items"]] == [mine.number]
    assert [row["name"] for row in by_school["rows"]] == ["Школа VKO-B-001"]
    assert [row["name"] for row in by_provider["rows"]] == ["Провайдер VKO-B-001"]
    # Contacts of his own school without the phone: that right is not in the role (ТЗ п. 15).
    assert [(item["full_name"], item["phone"]) for item in contacts["items"]] == [
        ("Директор B", None)
    ]

    # The school of another provider, its contacts and its incidents are «не найдено».
    for path in (
        f"/api/schools/{school_a.id}",
        f"/api/schools/{school_a.id}/contacts",
        f"/api/schools/{school_a.id}/incidents",
        f"/api/schools/{school_a.id}/devices",
    ):
        problem(await api_client.get(path, headers=provider), 404, "not_found")
    # Asking for the other provider by its id gives nothing, not his rows.
    foreign = (await line_of(session, school_a)).provider_id
    listed = await get(api_client, "/api/incidents", provider, provider_id=foreign)
    rows = await get(
        api_client, "/api/analytics", provider, level="school", region_id=school_a.region_id, **DAY
    )
    assert (listed["items"], rows["rows"]) == ([], [])


async def test_the_provider_works_an_incident_but_the_closing_is_not_his(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, school = await two_districts(session)
    incident = await an_incident(session, school, "INC-2026-000003")
    provider = await provider_of(session, school)
    district = bearer(await create_user(session, "district", region_id=school.region_id))
    path = f"/api/incidents/{incident.id}"

    moved = [
        ok(await change(api_client, incident, status, provider, comment))["status"]
        for status, comment in (
            ("in_progress", "Бригада выехала"),
            ("awaiting_info", "Ждём доступ в серверную"),
            ("in_progress", "Доступ получен"),
            ("resolved", "Заменили оптику"),
        )
    ]
    refused = problem(
        await change(api_client, incident, "closed", provider, "Готово"), 403, "forbidden"
    )
    closed = ok(await change(api_client, incident, "closed", district, "Проверено, работает"))

    assert moved == ["in_progress", "awaiting_info", "in_progress", "resolved"]
    assert "района" in refused["detail"]
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None
    # Every move of his is in the history under his name (ADR-007).
    card = ok(await api_client.get(path, headers=provider))
    assert [(event["kind"], event["to_status"]) for event in card["events"]] == [
        ("status_change", "in_progress"),
        ("status_change", "awaiting_info"),
        ("status_change", "in_progress"),
        ("status_change", "resolved"),
        ("status_change", "closed"),
    ]
    # Nobody moved the incident to «Передан поставщику», so there is no reaction time to count.
    assert card["provider_reaction_s"] is None


async def test_the_cabinet_has_no_administration_and_opens_no_incident(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, school = await two_districts(session)
    provider = await provider_of(session, school)
    line = await line_of(session, school)

    for path in ADMIN_PATHS:
        problem(await api_client.get(path, headers=provider), 403, "forbidden")
    # An incident is opened by hand by the district and above; the provider only works it.
    manual: dict[str, Any] = {
        "line_id": line.id,
        "metrics": ["download_mbps"],
        "started_at": datetime.now(UTC).isoformat(),
    }
    opened = await api_client.post("/api/incidents", json=manual, headers=provider)
    problem(opened, 403, "forbidden")

    me = ok(await api_client.get("/api/auth/me", headers=provider))

    # The panel hides a section by this list (web/src/app/sections.ts); the API checks it again.
    assert set(me["permissions"]) == set(ROLE_PERMISSIONS["provider"])
    assert me["role"] == "provider"
    assert "contacts:phone" not in me["permissions"]
    assert not [right for right in me["permissions"] if right.endswith(":manage")]


async def test_a_provider_of_a_reserve_line_gets_the_school_without_the_main_line(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Rule of the school-level fields for a provider (docs/known-limitations.md, T-03).

    School A is served by provider A on its main line and by provider R on the reserve one. The
    fields of the school — status, averages, last measurement, thresholds — are counted on the
    main line (ADR-012), and that line is not in the scope of provider R: he gets the school with
    «Нет данных» and his own line in the card, never the numbers of the line of provider A.
    """
    school_a, _ = await two_districts(session)
    reserve_provider = Provider(name="Провайдер резерва")
    session.add(reserve_provider)
    await session.flush()
    reserve = Line(school_id=school_a.id, provider_id=reserve_provider.id, status="reserve")
    session.add(reserve)
    await session.flush()
    provider = bearer(await create_user(session, "provider", provider_id=reserve_provider.id))

    schools = await get(api_client, "/api/schools", provider)
    lines = await get(api_client, f"/api/schools/{school_a.id}/lines", provider)
    card = await get(api_client, f"/api/schools/{school_a.id}", provider)

    [item] = schools["items"]
    assert item["school_code"] == "VKO-A-001"
    assert (item["status"], item["avg_download_mbps"], item["last_measured_at"]) == (
        "no_data",
        None,
        None,
    )
    # Only his own line, with his own name: the main line of provider A is not in his scope.
    assert [(line["status"], line["provider_name"]) for line in lines["items"]] == [
        ("reserve", "Провайдер резерва")
    ]
    assert card["latest_measurement"] is None
