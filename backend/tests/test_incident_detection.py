"""T-40: incidents by rules with hysteresis (ТЗ п. 18, п. 19; ADR-007).

Measurements go through the agent API, so each is judged on receipt against the global profile
of the migration (Download ≥ 20 Мбит/с …), and the detection runs after each of them as the
worker would, with the rules the migration creates: 3 violations in a row open an incident,
2 normal results in a row restore it; «Нет соединения» also opens after 30 minutes of silence.
Working hours are the default ones: Mon–Sat 08:00–18:00 Asia/Almaty (UTC+5).
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import apply_scope, clear_scope
from app.models import AuditLog, Device, Incident, IncidentEvent, IncidentRule, Line
from app.services.incidents import Detection, detect_line
from app.workers.celery_app import celery_app
from app.workers.tasks.incidents import DETECT_ALL, DETECT_LINE
from tests.factories import bearer, create_school, create_settings, create_user, primary_point
from tests.factories import register_device as register
from tests.test_agent_measurements import BATCH, MEASUREMENTS, measurement
from tests.test_agent_register import as_device

# Wednesday 16 September 2026, 10:00 in Asia/Almaty: inside working hours.
NOW = datetime(2026, 9, 16, 5, 0, tzinfo=UTC)
SLOT = timedelta(hours=3)

SLOW = {"download_mbps": 5.0}
FINE: dict[str, Any] = {}


class Agent:
    """A computer of a school on its main line that measures and is judged after each result."""

    def __init__(self, session: AsyncSession, client: AsyncClient, line: Line, token: str):
        self.session, self.client, self.line, self.token = session, client, line, token
        self.at = NOW - 20 * SLOT

    async def measure(self, values: dict[str, Any], **fields: Any) -> Detection:
        self.at += SLOT
        body = measurement(measured_at=self.at.isoformat(), **values, **fields)
        response = await self.client.post(MEASUREMENTS, json=body, headers=as_device(self.token))
        assert response.status_code == 201, response.text
        return await detect_line(self.session, self.line.id, now=self.at + timedelta(minutes=1))


async def an_agent(session: AsyncSession, client: AsyncClient, code: str = "VKO-I-001") -> Agent:
    school = await create_school(session, school_code=code)
    _, token = await register(session, await primary_point(session, school), device_uid=code)
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    return Agent(session, client, line, token)


async def rule_of(session: AsyncSession, metric: str) -> IncidentRule:
    """The rule of the oblast for ``metric``: the one the migration created."""
    return (
        await session.scalars(
            select(IncidentRule).where(
                IncidentRule.metric == metric, IncidentRule.scope == "global"
            )
        )
    ).one()


async def incidents_of(session: AsyncSession, line: Line) -> list[Incident]:
    return list(
        await session.scalars(
            select(Incident).where(Incident.line_id == line.id).order_by(Incident.id)
        )
    )


async def events_of(session: AsyncSession, incident_id: int) -> list[tuple[str, str | None]]:
    rows = await session.execute(
        select(IncidentEvent.kind, IncidentEvent.to_status)
        .where(IncidentEvent.incident_id == incident_id, IncidentEvent.author_user_id.is_(None))
        .order_by(IncidentEvent.id)
    )
    return [(kind, to_status) for kind, to_status in rows]


async def test_a_single_deviation_opens_nothing_the_third_in_a_row_opens_a_new_incident(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)

    # A deviation between norms is not a run: it never opens an incident.
    assert (await agent.measure(FINE)).opened == []
    assert (await agent.measure(SLOW)).opened == []
    assert (await agent.measure(FINE)).opened == []
    first = agent.at + SLOT
    assert (await agent.measure(SLOW)).opened == []
    assert (await agent.measure(SLOW)).opened == []
    third = await agent.measure(SLOW)

    assert len(third.opened) == 1
    incident = await session.get_one(Incident, third.opened[0])
    assert incident.status == "new"
    assert re.fullmatch(r"INC-2026-\d{6}", incident.number)
    assert incident.started_at == first
    assert incident.last_violation_at == agent.at
    assert incident.restored_at is None
    assert (incident.school_id, incident.provider_id) == (
        agent.line.school_id,
        agent.line.provider_id,
    )
    assert incident.rule_id == (await rule_of(session, "download_mbps")).id
    assert incident.basis_metrics == [{"metric": "download_mbps", "value": 5.0, "threshold": 20.0}]
    assert await events_of(session, incident.id) == [("created", "new")]
    # Only Download was violated: the rules of the other metrics opened nothing.
    assert [i.id for i in await incidents_of(session, agent.line)] == [incident.id]


async def test_the_fourth_violation_updates_the_open_incident_instead_of_opening_another(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)
    for _ in range(3):
        opened = (await agent.measure(SLOW)).opened

    fourth = await agent.measure(SLOW)

    assert fourth.opened == []
    assert fourth.updated == opened
    [incident] = await incidents_of(session, agent.line)
    assert incident.last_violation_at == agent.at
    # A rerun on the same data changes nothing: the beat and the task may both judge the line.
    again = await detect_line(session, agent.line.id, now=agent.at + timedelta(minutes=5))
    assert again == Detection()


async def test_two_normal_results_in_a_row_set_restored_at_one_does_not(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)
    for _ in range(3):
        opened = (await agent.measure(SLOW)).opened
    [incident_id] = opened

    # One norm between violations is not a recovery: the violation goes on (hysteresis).
    assert (await agent.measure(FINE)).restored == []
    assert (await agent.measure(SLOW)).updated == [incident_id]
    assert (await agent.measure(FINE)).restored == []
    recovered_at = agent.at
    restored = await agent.measure(FINE)

    assert restored.restored == [incident_id]
    incident = await session.get_one(Incident, incident_id)
    assert incident.restored_at == recovered_at
    assert incident.status == "new"  # the status is changed by people only (T-41)
    assert await events_of(session, incident_id) == [("created", "new"), ("restored", None)]

    # A new run is a new incident with its own number; it does not reach back to the old one.
    for _ in range(2):
        assert (await agent.measure(SLOW)).opened == []
    started = agent.at
    reopened = await agent.measure(SLOW)
    assert len(reopened.opened) == 1
    new = await session.get_one(Incident, reopened.opened[0])
    assert new.number != incident.number
    assert new.started_at == started - SLOT


async def test_an_edited_rule_applies_to_the_next_detection_and_is_audited(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)
    oblast = await create_user(session, "oblast")
    download = await rule_of(session, "download_mbps")

    response = await api_client.patch(
        f"/api/admin/incident-rules/{download.id}",
        json={"consecutive_violations": 2},
        headers=bearer(oblast),
    )
    assert response.status_code == 200, response.text

    assert (await agent.measure(SLOW)).opened == []
    assert len((await agent.measure(SLOW)).opened) == 1
    audit = (
        await session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "incident_rule", AuditLog.entity_id == download.id
            )
        )
    ).one()
    assert (audit.action, audit.user_id) == ("update", oblast.id)
    assert audit.changes == {"consecutive_violations": {"old": 3, "new": 2}}

    # A switched-off rule is not applied at all.
    ping = await rule_of(session, "ping_ms")
    ping.is_active = False
    await session.flush()
    for _ in range(4):
        detection = await agent.measure({"ping_ms": 400.0})
    assert all(i.rule_id != ping.id for i in await incidents_of(session, agent.line))
    assert detection.opened == []


async def test_a_duration_rule_opens_after_t_minutes_from_the_first_violation(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)
    jitter = await rule_of(session, "jitter_ms")
    jitter.consecutive_violations = None
    jitter.duration_min = 4 * 60
    await session.flush()

    assert (await agent.measure({"jitter_ms": 80.0})).opened == []
    assert (await agent.measure({"jitter_ms": 80.0})).opened == []  # 3 hours
    opened = (await agent.measure({"jitter_ms": 80.0})).opened  # 6 hours

    [incident] = await incidents_of(session, agent.line)
    assert opened == [incident.id]
    assert incident.rule_id == jitter.id
    assert incident.started_at == agent.at - 2 * SLOT


async def test_wifi_and_unmeasured_metrics_say_nothing_offline_results_are_no_connection(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)

    # Wi-Fi measures the air, not the line (ADR-012).
    for _ in range(3):
        assert (await agent.measure(SLOW, iface_type="wifi")).opened == []
    # A metric the agent did not measure neither breaks the run nor counts in it.
    assert (await agent.measure(SLOW)).opened == []
    assert (await agent.measure({"download_mbps": None})).opened == []
    assert (await agent.measure(SLOW)).opened == []
    assert len((await agent.measure(SLOW)).opened) == 1

    offline = {name: None for name in ("download_mbps", "upload_mbps", "ping_ms", "jitter_ms")}
    offline |= {"packet_loss_pct": None, "connection_status": "offline"}
    assert (await agent.measure(offline)).opened == []
    # Two offline results a slot apart are 3 hours without connection: past the 30 minutes of
    # the rule before the third one comes.
    detection = await agent.measure(offline)
    no_connection = await rule_of(session, "no_connection")
    [incident] = [i for i in await incidents_of(session, agent.line) if i.id in detection.opened]
    assert incident.rule_id == no_connection.id
    assert incident.started_at == agent.at - SLOT
    assert incident.basis_metrics == [{"metric": "no_connection", "value": None, "threshold": None}]


async def test_silence_in_working_hours_for_30_minutes_is_no_connection(
    session: AsyncSession,
) -> None:
    await create_settings(session)
    school = await create_school(session, school_code="VKO-I-HB")
    device, _ = await register(session, await primary_point(session, school), device_uid="HB")
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()

    async def silent_for(minutes: int, now: datetime = NOW) -> Detection:
        await session.execute(
            Device.__table__.update()
            .where(Device.id == device.id)
            .values(last_seen_at=now - timedelta(minutes=minutes))
        )
        return await detect_line(session, line.id, now=now)

    # Silence of 20 minutes is «Нет соединения» on the map, but not an incident yet.
    assert (await silent_for(20)).opened == []
    # 22:00 in Almaty: a computer switched off for the night is not a broken line.
    assert (await silent_for(120, NOW + timedelta(hours=12))).opened == []
    # Silence since yesterday evening counts from 08:00 today: at 08:20 it is 20 minutes old.
    morning = datetime(2026, 9, 16, 3, 20, tzinfo=UTC)
    assert (await silent_for(15 * 60, morning)).opened == []

    opened = (await silent_for(40)).opened

    [incident] = await incidents_of(session, line)
    assert opened == [incident.id]
    assert incident.rule_id == (await rule_of(session, "no_connection")).id
    assert incident.started_at == NOW - timedelta(minutes=40)
    assert incident.last_violation_at == NOW
    # While the line stays silent the incident is moved on, not opened again.
    later = await detect_line(session, line.id, now=NOW + timedelta(minutes=5))
    assert later.updated == [incident.id] and later.opened == []


async def test_a_rule_of_a_school_replaces_the_global_rule_of_its_metric_for_its_lines_only(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """T-85: two violations open an incident at the school with its own rule, not elsewhere."""
    await create_settings(session)
    satellite = await an_agent(session, api_client, code="VKO-I-SAT")
    ordinary = await an_agent(session, api_client, code="VKO-I-ORD")
    own = IncidentRule(
        name="Download по спутнику",
        metric="download_mbps",
        scope="school",
        school_id=satellite.line.school_id,
        consecutive_violations=2,
        recovery_normal_count=1,
    )
    session.add(own)
    await session.flush()

    assert (await satellite.measure(SLOW)).opened == []
    by_own = (await satellite.measure(SLOW)).opened
    assert (await ordinary.measure(SLOW)).opened == []
    assert (await ordinary.measure(SLOW)).opened == []
    by_global = (await ordinary.measure(SLOW)).opened

    [incident] = await incidents_of(session, satellite.line)
    assert by_own == [incident.id] and incident.rule_id == own.id
    [other] = await incidents_of(session, ordinary.line)
    assert by_global == [other.id]
    assert other.rule_id == (await rule_of(session, "download_mbps")).id
    # The global rule of the same metric opens nothing more at the school with its own rule.
    assert (await satellite.measure(SLOW)).opened == []
    assert [i.id for i in await incidents_of(session, satellite.line)] == [incident.id]


async def test_an_incident_of_a_global_rule_is_restored_after_the_school_got_its_own_rule(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """A new rule of a school never leaves the incident of the global rule hanging (T-85)."""
    await create_settings(session)
    agent = await an_agent(session, api_client, code="VKO-I-OWN")
    for _ in range(3):
        opened = (await agent.measure(SLOW)).opened
    [by_global] = opened
    own = IncidentRule(
        name="Download школы",
        metric="download_mbps",
        scope="school",
        school_id=agent.line.school_id,
        consecutive_violations=2,
        recovery_normal_count=2,
    )
    session.add(own)
    await session.flush()

    # The old incident is moved on and restored by the global rule as before.
    assert (await agent.measure(SLOW)).updated == [by_global]
    assert (await agent.measure(FINE)).restored == []
    assert (await agent.measure(FINE)).restored == [by_global]
    # From now on the rule of the school opens the incidents of the line.
    assert (await agent.measure(SLOW)).opened == []
    reopened = (await agent.measure(SLOW)).opened

    assert len(reopened) == 1
    incident = await session.get_one(Incident, reopened[0])
    assert incident.rule_id == own.id


async def test_new_measurements_hand_their_line_to_the_detection(
    session: AsyncSession, api_client: AsyncClient, detection_queue: list[int]
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)
    body = measurement(measured_at=NOW.isoformat())

    await api_client.post(MEASUREMENTS, json=body, headers=as_device(agent.token))
    await api_client.post(MEASUREMENTS, json=body, headers=as_device(agent.token))  # 409
    await api_client.post(BATCH, json={"items": [body]}, headers=as_device(agent.token))
    await api_client.post(
        BATCH,
        json={"items": [measurement(measured_at=NOW.isoformat()) for _ in range(3)]},
        headers=as_device(agent.token),
    )

    # A repeat stores nothing, so it has nothing new to judge; a batch is judged once.
    assert detection_queue == [agent.line.id, agent.line.id]


def test_detection_runs_after_measurements_and_every_5_minutes() -> None:
    schedule = {
        entry["task"]: entry["schedule"] for entry in celery_app.conf.beat_schedule.values()
    }
    assert schedule[DETECT_ALL] == 5 * 60
    assert {DETECT_LINE, DETECT_ALL} <= set(celery_app.tasks)


async def test_a_stranger_does_not_see_the_incidents_of_a_line(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client)
    other = await create_school(session, school_code="VKO-I-002")
    for _ in range(3):
        opened = (await agent.measure(SLOW)).opened
    await session.flush()

    async def visible(scope: str) -> tuple[int, int]:
        await apply_scope(session, scope)
        try:
            incidents = await session.scalar(
                select(func.count()).select_from(Incident).where(Incident.id.in_(opened))
            )
            events = await session.scalar(
                select(func.count())
                .select_from(IncidentEvent)
                .where(IncidentEvent.incident_id.in_(opened))
            )
            return incidents or 0, events or 0
        finally:
            await clear_scope(session)

    assert await visible(f"region:{other.region_id}") == (0, 0)
    assert await visible(f"school:{other.id}") == (0, 0)
    assert await visible(f"provider:{agent.line.provider_id}") == (1, 1)
    assert await visible(f"school:{agent.line.school_id}") == (1, 1)
    assert await visible("all") == (1, 1)
