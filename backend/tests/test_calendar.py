"""T-70: календарь каникул, праздников и плановых работ (docs/design/README.md §6.5).

В дни каникул и праздника замеры принимаются и хранятся, но доступность не считается и инциденты
не создаются, а тишина агента показывается как «Нет данных», а не «Нет соединения» (ТЗ п. 13).
Окно плановых работ поставщика не входит в его оценку (ТЗ п. 14). Область действия события —
вся область, район или школа, и RLS держит район внутри его событий (ADR-008).

Время везде подставляется, а не ожидается: каждый расчёт принимает момент или период.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import apply_scope, clear_scope
from app.models import CalendarEvent, Line, School
from app.services.availability import school_availability
from app.services.calendar import is_quiet
from app.services.status import school_status
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)
from tests.test_incident_detection import SLOW, an_agent
from tests.test_overview import WORKDAY, get
from tests.test_providers_score import DAY, SCORE, provider_of, slow_answer, two_providers
from tests.test_school_status import heartbeats_of_the_working_day

CALENDAR = "/api/admin/calendar"
DAY_START = WORKDAY.replace(hour=0, minute=0, second=0, microsecond=0)
NEXT_DAY = DAY_START + timedelta(days=1)


async def add_event(
    session: AsyncSession,
    *,
    kind: str,
    scope: str,
    starts_at: datetime,
    ends_at: datetime,
    title: str = "Событие",
    **target: int | None,
) -> CalendarEvent:
    """Row of the calendar, as the administration of T-70 writes it."""
    event = CalendarEvent(
        kind=kind, scope=scope, starts_at=starts_at, ends_at=ends_at, title=title, **target
    )
    session.add(event)
    await session.flush()
    return event


async def school_of(session: AsyncSession, line_id: int) -> int:
    school_id = await session.scalar(select(Line.school_id).where(Line.id == line_id))
    assert school_id is not None
    return school_id


async def test_a_vacation_of_a_school_opens_no_incident(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    agent = await an_agent(session, api_client, "VKO-C-001")
    school_id = await school_of(session, agent.line.id)
    # The whole history the agent is about to measure falls inside the vacation of its school.
    await add_event(
        session,
        kind="vacation",
        scope="school",
        school_id=school_id,
        starts_at=agent.at - timedelta(days=30),
        ends_at=agent.at + timedelta(days=30),
        title="Осенние каникулы",
    )

    opened = [(await agent.measure(SLOW)).opened for _ in range(4)]

    # Four violations in a row would open an incident on an ordinary day; in the vacations the
    # readings say nothing about the line at all.
    assert opened == [[], [], [], []]
    assert await is_quiet(session, school_id, agent.at) == "vacation"


async def test_a_vacation_takes_the_days_of_its_school_out_of_availability(
    session: AsyncSession,
) -> None:
    await create_settings(session)
    school = await create_school(session, school_code="VKO-V-001")
    device, _ = await register_device(session, await primary_point(session, school))
    # A working day the school was silent the whole of: without the calendar it would be down.
    await heartbeats_of_the_working_day(
        session, device, DAY_START, gap=(DAY_START.replace(hour=8), DAY_START.replace(hour=18))
    )
    await add_event(
        session,
        kind="vacation",
        scope="school",
        school_id=school.id,
        starts_at=DAY_START,
        ends_at=NEXT_DAY,
        title="Осенние каникулы",
    )

    result = await school_availability(session, school.id, start=DAY_START, end=NEXT_DAY)

    # Nothing was observed, so there is no percentage at all: «нет данных» is not «лежало».
    assert (result.observed_s, result.downtime_s, result.uptime_pct) == (0, 0, None)


async def test_a_holiday_of_the_oblast_freezes_every_school(session: AsyncSession) -> None:
    await create_settings(session)
    first = await create_school(session, school_code="VKO-H-001")
    second = await create_school(session, school_code="VKO-H-002")
    for school in (first, second):
        device, _ = await register_device(
            session, await primary_point(session, school), device_uid=school.school_code
        )
        await heartbeats_of_the_working_day(
            session, device, DAY_START, gap=(DAY_START.replace(hour=8), DAY_START.replace(hour=18))
        )
    await add_event(
        session,
        kind="holiday",
        scope="oblast",
        starts_at=DAY_START,
        ends_at=NEXT_DAY,
        title="День Республики",
    )

    for school in (first, second):
        result = await school_availability(session, school.id, start=DAY_START, end=NEXT_DAY)
        assert (result.observed_s, result.uptime_pct) == (0, None)
        assert await is_quiet(session, school.id, WORKDAY) == "holiday"


async def test_silence_in_a_quiet_interval_is_no_data_not_offline(session: AsyncSession) -> None:
    await create_settings(session)
    school = await create_school(session, school_code="VKO-Q-001")
    device, _ = await register_device(session, await primary_point(session, school))
    # Last heard yesterday: in working hours of an ordinary day that is «Нет соединения».
    device.last_seen_at = WORKDAY - timedelta(days=1)
    await session.flush()

    assert await school_status(session, school.id, now=WORKDAY) == "offline"

    await add_event(
        session,
        kind="holiday",
        scope="oblast",
        starts_at=DAY_START,
        ends_at=NEXT_DAY,
        title="День Республики",
    )

    assert await school_status(session, school.id, now=WORKDAY) == "no_data"


async def test_a_planned_works_window_drops_out_of_the_score(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_providers(session)
    await slow_answer(session, school_a)
    oblast = bearer(await create_user(session, "oblast"))

    answered: dict[str, Any] = await get(api_client, SCORE, oblast, **DAY)
    [row_a] = [row for row in answered["rows"] if row["id"] == await provider_of(session, school_a)]
    assert row_a["reaction_median_s"] == 12 * 3600

    # The incident started inside a window the provider announced: it is not his reaction time.
    await add_event(
        session,
        kind="planned_works",
        scope="oblast",
        provider_id=await provider_of(session, school_a),
        starts_at=WORKDAY - timedelta(days=1),
        ends_at=WORKDAY,
        title="Замена оборудования узла",
    )

    excluded: dict[str, Any] = await get(api_client, SCORE, oblast, **DAY)
    [row] = [row for row in excluded["rows"] if row["id"] == row_a["id"]]
    assert row["reaction_median_s"] is None
    assert row["score"] is not None and row["score"] > row_a["score"]


async def test_works_of_one_school_do_not_excuse_the_whole_oblast(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """A window announced for one school leaves the incidents of the other schools in the score."""
    school_a, school_b = await two_providers(session)
    await slow_answer(session, school_a)
    oblast = bearer(await create_user(session, "oblast"))

    # The provider of school A announces works at school B alone: school A is not covered.
    await add_event(
        session,
        kind="planned_works",
        scope="school",
        school_id=school_b.id,
        provider_id=await provider_of(session, school_a),
        starts_at=WORKDAY - timedelta(days=1),
        ends_at=WORKDAY,
        title="Замена оборудования узла",
    )

    answered: dict[str, Any] = await get(api_client, SCORE, oblast, **DAY)
    [row] = [row for row in answered["rows"] if row["id"] == await provider_of(session, school_a)]
    assert row["reaction_median_s"] == 12 * 3600


async def test_a_district_sees_and_edits_only_its_own_events(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    mine = await create_school(session, school_code="VKO-D-001")
    other = await create_school(session, school_code="VKO-D-002")
    await add_event(
        session,
        kind="vacation",
        scope="district",
        region_id=mine.region_id,
        starts_at=DAY_START,
        ends_at=NEXT_DAY,
        title="Каникулы своего района",
    )
    await add_event(
        session,
        kind="vacation",
        scope="district",
        region_id=other.region_id,
        starts_at=DAY_START,
        ends_at=NEXT_DAY,
        title="Каникулы чужого района",
    )
    await add_event(
        session,
        kind="holiday",
        scope="oblast",
        starts_at=DAY_START,
        ends_at=NEXT_DAY,
        title="День Республики",
    )
    await session.commit()

    await apply_scope(session, f"region:{mine.region_id}")
    try:
        titles = list(await session.scalars(select(CalendarEvent.title).order_by(CalendarEvent.id)))
    finally:
        await clear_scope(session)

    # The events of the oblast are everybody's; the events of another district are not.
    assert titles == ["Каникулы своего района", "День Республики"]

    # The resource itself is administration: a district user does not reach it at all (ТЗ п. 16).
    district = bearer(
        await create_user(session, "district", email="d@example.kz", region_id=mine.region_id)
    )
    denied = await api_client.get(CALENDAR, headers=district)
    assert denied.status_code == 403, denied.text


async def test_the_calendar_is_filled_from_a_table(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session, school_code="VKO-I-100")
    admin = bearer(await create_user(session, "admin"))
    text = (
        "kind,title,start,end,school_code\n"
        "vacation,Осенние каникулы,2026-10-26,2026-11-01,\n"
        f"holiday,День Республики,2026-10-25,2026-10-25,{school.school_code}\n"
        "vacation,Кривая строка,вчера,2026-11-01,\n"
    )

    response = await api_client.post(f"{CALENDAR}/import", headers=admin, json={"text": text})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1
    events = list(await session.scalars(select(CalendarEvent).order_by(CalendarEvent.starts_at)))
    # The last day of the order is a whole local day, so the vacation ends at midnight after it.
    assert [(event.kind, event.scope) for event in events] == [
        ("holiday", "school"),
        ("vacation", "oblast"),
    ]
    assert events[1].ends_at == datetime(2026, 11, 1, 19, 0, tzinfo=UTC)


async def test_a_school_out_of_the_calendar_is_judged_as_usual(session: AsyncSession) -> None:
    await create_settings(session)
    school: School = await create_school(session, school_code="VKO-N-001")

    assert await is_quiet(session, school.id, WORKDAY) is None
