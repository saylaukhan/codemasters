"""T-41: the incident card — list, statuses, history, comments, durations (ТЗ п. 19; ADR-007).

Incidents are put straight into the database in the status a test needs, as the detection of
T-40 or earlier requests would leave them; everything a person does goes through the API. The
transition table is written out here on its own, not taken from the service, so a change of
one of them shows up as a failing test.
"""

import itertools
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Incident, IncidentRule, Line, School
from app.services.incident_card import AUTO_CLOSE_AFTER, AUTO_CLOSE_COMMENT, close_resolved
from app.workers.celery_app import celery_app
from app.workers.tasks.incidents import CLOSE_RESOLVED
from tests.factories import bearer, create_school, create_settings, create_user
from tests.test_admin_incident_rules import ok, problem

INCIDENTS = "/api/incidents"
STATUSES = ["new", "sent_to_provider", "in_progress", "awaiting_info", "resolved", "closed"]
# Forward in the order of ТЗ п. 19 with the intermediate statuses optional, «Закрыт» only from
# «Устранён»; back only to «В работе»; nothing leaves «Закрыт».
ALLOWED = {
    ("new", "sent_to_provider"),
    ("new", "in_progress"),
    ("new", "awaiting_info"),
    ("new", "resolved"),
    ("sent_to_provider", "in_progress"),
    ("sent_to_provider", "awaiting_info"),
    ("sent_to_provider", "resolved"),
    ("in_progress", "awaiting_info"),
    ("in_progress", "resolved"),
    ("awaiting_info", "in_progress"),
    ("awaiting_info", "resolved"),
    ("resolved", "in_progress"),
    ("resolved", "closed"),
}

STARTED = datetime(2026, 9, 16, 5, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)
numbers = itertools.count(1)


async def line_of(session: AsyncSession, school: School) -> Line:
    return (await session.scalars(select(Line).where(Line.school_id == school.id))).one()


async def an_incident(
    session: AsyncSession, school: School, *, status: str = "new", **fields: Any
) -> Incident:
    """Incident of the main line of ``school``, as the detection opens it, in ``status``."""
    line = await line_of(session, school)
    incident = Incident(
        number=f"INC-1999-{next(numbers):06d}",
        status=status,
        line_id=line.id,
        school_id=school.id,
        provider_id=line.provider_id,
        basis_metrics=[{"metric": "download_mbps", "value": 5.0, "threshold": 20.0}],
        **{"started_at": STARTED} | fields,
    )
    session.add(incident)
    await session.flush()
    return incident


async def change(
    client: AsyncClient,
    incident: Incident,
    status: str,
    headers: dict[str, str],
    comment: str | None = None,
) -> Response:
    body = {"status": status} | ({"comment": comment} if comment else {})
    return await client.post(f"{INCIDENTS}/{incident.id}/status", json=body, headers=headers)


def at(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def fields(response: Response) -> list[str]:
    return [error["field"] for error in problem(response, 422, "validation_error")["errors"]]


@pytest.mark.parametrize(("source", "target"), list(itertools.product(STATUSES, STATUSES)))
async def test_only_the_transitions_of_the_table_are_allowed(
    session: AsyncSession, api_client: AsyncClient, source: str, target: str
) -> None:
    school = await create_school(session)
    restored = STARTED + HOUR if source in ("resolved", "closed") else None
    incident = await an_incident(session, school, status=source, restored_at=restored)
    admin = bearer(await create_user(session, "admin"))

    response = await change(api_client, incident, target, admin, comment="Проверено")

    if (source, target) in ALLOWED:
        card = ok(response)
        assert card["status"] == target
        assert [(e["kind"], e["from_status"], e["to_status"]) for e in card["events"]] == [
            ("status_change", source, target)
        ]
    else:
        assert "не допускается" in problem(response, 409, "invalid_status_transition")["detail"]
        card = ok(await api_client.get(f"{INCIDENTS}/{incident.id}", headers=admin))
        assert (card["status"], card["events"]) == (source, [])


async def test_a_status_change_is_validated_and_only_the_district_and_above_close(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    line = await line_of(session, school)
    incident = await an_incident(session, school, status="resolved", restored_at=STARTED + HOUR)
    provider = bearer(await create_user(session, "provider", provider_id=line.provider_id))
    school_user = bearer(await create_user(session, "school", school_id=school.id))

    assert fields(await change(api_client, incident, "fixed", provider)) == ["status"]
    # «Закрыт» needs a comment (DESIGN.md §3.17), whoever closes: a check of the whole body.
    assert fields(await change(api_client, incident, "closed", provider)) == ["body"]
    problem(await change(api_client, incident, "closed", provider, "Готово"), 403, "forbidden")
    problem(await change(api_client, incident, "in_progress", school_user), 403, "forbidden")
    problem(
        await change(api_client, incident, "resolved", provider), 409, "invalid_status_transition"
    )
    # The provider reports the fix and may take the incident back into work.
    assert (
        ok(await change(api_client, incident, "in_progress", provider))["status"] == "in_progress"
    )
    problem(
        await api_client.post(
            f"{INCIDENTS}/0/status", json={"status": "resolved"}, headers=provider
        ),
        404,
        "not_found",
    )


async def test_transitions_set_the_moments_and_write_the_history(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    incident = await an_incident(session, school)
    user = await create_user(session, "district", region_id=school.region_id)
    district = bearer(user)
    before = datetime.now(UTC)

    sent = ok(await change(api_client, incident, "sent_to_provider", district))
    sent_at = at(sent["sent_to_provider_at"])
    assert sent_at is not None and before <= sent_at <= datetime.now(UTC)
    assert (sent["restored_at"], sent["duration_s"], sent["provider_reaction_s"]) == (
        None,
        None,
        None,
    )

    resolved = ok(await change(api_client, incident, "resolved", district, "Заменили кабель"))
    restored_at = at(resolved["restored_at"])
    assert restored_at is not None and restored_at >= sent_at
    assert resolved["duration_s"] == int((restored_at - STARTED).total_seconds())
    assert resolved["provider_reaction_s"] == int((restored_at - sent_at).total_seconds())

    # The problem came back before the closing: it is not restored any more.
    back = ok(await change(api_client, incident, "in_progress", district, "Снова медленно"))
    assert (back["restored_at"], back["duration_s"], back["provider_reaction_s"]) == (
        None,
        None,
        None,
    )
    assert at(back["sent_to_provider_at"]) == sent_at

    ok(await change(api_client, incident, "resolved", district))
    closed = ok(await change(api_client, incident, "closed", district, "Школа подтвердила"))
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None
    assert [
        (e["kind"], e["from_status"], e["to_status"], e["comment"], e["author_user_id"])
        for e in closed["events"]
    ] == [
        ("status_change", "new", "sent_to_provider", None, user.id),
        ("status_change", "sent_to_provider", "resolved", "Заменили кабель", user.id),
        ("status_change", "resolved", "in_progress", "Снова медленно", user.id),
        ("status_change", "in_progress", "resolved", None, user.id),
        ("status_change", "resolved", "closed", "Школа подтвердила", user.id),
    ]
    assert {e["author_user_name"] for e in closed["events"]} == {user.full_name}


async def test_the_durations_count_from_the_moments_of_the_detection(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    incident = await an_incident(
        session,
        school,
        status="sent_to_provider",
        sent_to_provider_at=STARTED + HOUR,
        restored_at=STARTED + 3 * HOUR,
    )
    late = await an_incident(
        session, school, sent_to_provider_at=STARTED + 4 * HOUR, restored_at=STARTED + 3 * HOUR
    )
    oblast = bearer(await create_user(session, "oblast"))

    # restored_at set by the detection stays: «Устранён» does not move it to now.
    resolved = ok(await change(api_client, incident, "resolved", oblast))
    assert at(resolved["restored_at"]) == STARTED + 3 * HOUR
    assert (resolved["duration_s"], resolved["provider_reaction_s"]) == (3 * 3600, 2 * 3600)
    # Restored before it was sent to the provider: no reaction time.
    card = ok(await api_client.get(f"{INCIDENTS}/{late.id}", headers=oblast))
    assert (card["duration_s"], card["provider_reaction_s"]) == (3 * 3600, None)


async def test_a_rule_incident_does_not_come_back_over_a_newer_open_one(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    rule_id = await session.scalar(
        select(IncidentRule.id).where(IncidentRule.metric == "download_mbps")
    )
    old = await an_incident(
        session, school, status="resolved", rule_id=rule_id, restored_at=STARTED + HOUR
    )
    newer = await an_incident(session, school, rule_id=rule_id, started_at=STARTED + 2 * HOUR)
    oblast = bearer(await create_user(session, "oblast"))

    refused = problem(
        await change(api_client, old, "in_progress", oblast), 409, "invalid_status_transition"
    )
    assert newer.number in refused["detail"]

    ok(await change(api_client, newer, "resolved", oblast))
    assert ok(await change(api_client, old, "in_progress", oblast))["restored_at"] is None


async def test_a_comment_is_added_to_the_history_without_changing_the_status(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    line = await line_of(session, school)
    incident = await an_incident(session, school, status="sent_to_provider")
    user = await create_user(session, "provider", provider_id=line.provider_id)
    school_user = bearer(await create_user(session, "school", school_id=school.id))
    path = f"{INCIDENTS}/{incident.id}/comments"

    event = ok(
        await api_client.post(path, json={"comment": "Бригада выехала"}, headers=bearer(user)),
        201,
    )
    problem(
        await api_client.post(path, json={"comment": "?"}, headers=school_user), 403, "forbidden"
    )

    assert (
        event["kind"],
        event["comment"],
        event["author_user_id"],
        event["author_user_name"],
    ) == (
        "comment",
        "Бригада выехала",
        user.id,
        user.full_name,
    )
    assert (event["from_status"], event["to_status"]) == (None, None)
    card = ok(await api_client.get(f"{INCIDENTS}/{incident.id}", headers=school_user))
    assert card["status"] == "sent_to_provider"
    assert [e["id"] for e in card["events"]] == [event["id"]]


async def test_an_incident_is_created_by_hand_from_the_school_card(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    line = await line_of(session, school)
    other = await create_school(session, school_code="VKO-UK-002")
    user = await create_user(session, "district", region_id=school.region_id)
    district = bearer(user)
    responsible = await create_user(
        session, "district", email="duty@example.kz", region_id=school.region_id
    )
    blocked = await create_user(session, "oblast", email="gone@example.kz", is_active=False)
    body = {
        "line_id": line.id,
        "metrics": ["download_mbps", "ping_ms"],
        "description": "Жалобы учителей на медленный интернет",
        "started_at": STARTED.isoformat(),
        "responsible_user_id": responsible.id,
    }

    created = ok(await api_client.post(INCIDENTS, json=body, headers=district), 201)

    assert re.fullmatch(r"INC-\d{4}-\d{6}", created["number"])
    assert {
        key: created[key]
        for key in ("status", "rule_id", "school_id", "school_code", "line_id", "line_status")
    } == {
        "status": "new",
        "rule_id": None,
        "school_id": school.id,
        "school_code": school.school_code,
        "line_id": line.id,
        "line_status": "main",
    }
    assert (created["provider_id"], created["provider_name"]) == (
        line.provider_id,
        f"Провайдер {school.school_code}",
    )
    assert created["basis_metrics"] == [
        {"metric": "download_mbps", "value": None, "threshold": None},
        {"metric": "ping_ms", "value": None, "threshold": None},
    ]
    assert at(created["started_at"]) == STARTED
    assert (created["responsible_user_id"], created["responsible_user_name"]) == (
        responsible.id,
        responsible.full_name,
    )
    assert [(e["kind"], e["to_status"], e["author_user_id"]) for e in created["events"]] == [
        ("created", "new", user.id)
    ]
    listed = ok(await api_client.get(f"/api/schools/{school.id}/incidents", headers=district))
    assert [item["id"] for item in listed["items"]] == [created["id"]]

    # A line of another district is unknown to this user, as a line that does not exist.
    other_line = await line_of(session, other)
    wrong = [
        ({"line_id": other_line.id}, "line_id"),
        ({"line_id": 0}, "line_id"),
        ({"started_at": (datetime.now(UTC) + HOUR).isoformat()}, "started_at"),
        ({"responsible_user_id": blocked.id}, "responsible_user_id"),
    ]
    for change_, field in wrong:
        response = await api_client.post(INCIDENTS, json=body | change_, headers=district)
        assert fields(response) == [field], change_
    provider = bearer(await create_user(session, "provider", provider_id=line.provider_id))
    problem(await api_client.post(INCIDENTS, json=body, headers=provider), 403, "forbidden")


async def test_the_responsible_and_the_description_are_changed_with_audit(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    incident = await an_incident(session, school)
    oblast = bearer(await create_user(session, "oblast"))
    responsible = await create_user(session, "district", region_id=school.region_id)
    path = f"{INCIDENTS}/{incident.id}"

    assigned = ok(
        await api_client.patch(path, json={"responsible_user_id": responsible.id}, headers=oblast)
    )
    described = ok(await api_client.patch(path, json={"description": "Обрыв"}, headers=oblast))
    cleared = ok(await api_client.patch(path, json={"responsible_user_id": None}, headers=oblast))

    assert assigned["responsible_user_name"] == responsible.full_name
    assert described["responsible_user_id"] == responsible.id
    assert (cleared["responsible_user_id"], cleared["description"]) == (None, "Обрыв")
    assert fields(
        await api_client.patch(path, json={"responsible_user_id": 0}, headers=oblast)
    ) == ["responsible_user_id"]
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_id, AuditLog.changes)
        .where(AuditLog.entity_type == "incident")
        .order_by(AuditLog.id)
    )
    assert [tuple(row) for row in rows] == [
        ("update", incident.id, {"responsible_user_id": {"old": None, "new": responsible.id}}),
        ("update", incident.id, {"description": {"old": None, "new": "Обрыв"}}),
        ("update", incident.id, {"responsible_user_id": {"old": responsible.id, "new": None}}),
    ]


async def test_the_list_is_filtered_and_newest_first(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a = await create_school(session, school_code="VKO-L-001")
    school_b = await create_school(session, school_code="VKO-L-002")
    line_a, line_b = await line_of(session, school_a), await line_of(session, school_b)
    first = await an_incident(session, school_a)
    second = await an_incident(session, school_a, status="in_progress", started_at=STARTED + HOUR)
    third = await an_incident(
        session,
        school_b,
        status="resolved",
        started_at=STARTED + 2 * HOUR,
        restored_at=STARTED + 3 * HOUR,
    )
    oblast = bearer(await create_user(session, "oblast"))

    async def ids(path: str = INCIDENTS, **params: Any) -> list[int]:
        page = ok(await api_client.get(path, params=params, headers=oblast))
        assert page["total"] == len(page["items"])
        return [item["id"] for item in page["items"]]

    assert await ids() == [third.id, second.id, first.id]
    assert await ids(status=["new", "resolved"]) == [third.id, first.id]
    assert await ids(school_id=school_a.id) == [second.id, first.id]
    assert await ids(region_id=school_b.region_id) == [third.id]
    assert await ids(provider_id=line_b.provider_id) == [third.id]
    assert await ids(line_id=line_a.id) == [second.id, first.id]
    assert await ids(q=third.number.removeprefix("INC-1999-")) == [third.id]
    assert await ids(q="inc-1999") == [third.id, second.id, first.id]
    period = {
        "period_from": (STARTED + HOUR).isoformat(),
        "period_to": (STARTED + 2 * HOUR).isoformat(),
    }
    assert await ids(**period) == [second.id]
    assert await ids(f"/api/schools/{school_a.id}/incidents") == [second.id, first.id]
    problem(
        await api_client.get(f"/api/schools/{school_b.id + 1000}/incidents", headers=oblast),
        404,
        "not_found",
    )

    page = ok(await api_client.get(INCIDENTS, params={"page_size": 1}, headers=oblast))
    assert page["total"] == 3
    [item] = page["items"]
    assert {
        key: item[key]
        for key in ("school_code", "school_name", "line_status", "provider_name", "duration_s")
    } == {
        "school_code": "VKO-L-002",
        "school_name": "Школа VKO-L-002",
        "line_status": "main",
        "provider_name": "Провайдер VKO-L-002",
        "duration_s": 3600,
    }


@pytest.mark.parametrize("role", ["district", "provider"])
async def test_a_stranger_does_not_see_an_incident(
    session: AsyncSession, api_client: AsyncClient, role: str
) -> None:
    mine = await create_school(session, school_code="VKO-S-001")
    other = await create_school(session, school_code="VKO-S-002")
    own = await an_incident(session, mine)
    foreign = await an_incident(session, other)
    scope = {
        "district": {"region_id": mine.region_id},
        "provider": {"provider_id": (await line_of(session, mine)).provider_id},
    }[role]
    user = bearer(await create_user(session, role, **scope))

    listed = ok(await api_client.get(INCIDENTS, headers=user))
    assert [item["id"] for item in listed["items"]] == [own.id]
    ok(await api_client.get(f"{INCIDENTS}/{own.id}", headers=user))
    path = f"{INCIDENTS}/{foreign.id}"
    for method, url, body in [
        ("GET", path, None),
        ("PATCH", path, {"description": "Чужой"}),
        ("POST", f"{path}/status", {"status": "in_progress"}),
        ("POST", f"{path}/comments", {"comment": "Чужой"}),
        ("GET", f"/api/schools/{other.id}/incidents", None),
    ]:
        response = await api_client.request(method, url, json=body, headers=user)
        problem(response, 404, "not_found")


async def test_a_resolved_incident_is_closed_after_24_hours(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    incident = await an_incident(session, school, status="in_progress")
    untouched = await an_incident(session, school, status="awaiting_info")
    district = bearer(await create_user(session, "district", region_id=school.region_id))
    ok(await change(api_client, incident, "resolved", district))
    resolved_at = datetime.now(UTC)

    assert await close_resolved(session, now=resolved_at + AUTO_CLOSE_AFTER - HOUR / 60) == []
    closed = await close_resolved(session, now=resolved_at + AUTO_CLOSE_AFTER + HOUR / 60)

    assert closed == [incident.id]
    card = ok(await api_client.get(f"{INCIDENTS}/{incident.id}", headers=district))
    assert card["status"] == "closed"
    assert at(card["closed_at"]) == resolved_at + AUTO_CLOSE_AFTER + HOUR / 60
    last = card["events"][-1]
    assert (
        last["kind"],
        last["from_status"],
        last["to_status"],
        last["comment"],
        last["author_user_id"],
    ) == ("status_change", "resolved", "closed", AUTO_CLOSE_COMMENT, None)
    other = ok(await api_client.get(f"{INCIDENTS}/{untouched.id}", headers=district))
    assert other["status"] == "awaiting_info"


def test_the_auto_close_runs_every_15_minutes() -> None:
    schedule = {
        entry["task"]: entry["schedule"] for entry in celery_app.conf.beat_schedule.values()
    }
    assert schedule[CLOSE_RESOLVED] == 15 * 60
    assert CLOSE_RESOLVED in celery_app.tasks
