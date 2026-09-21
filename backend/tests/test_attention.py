"""T-60: «Требуют внимания» of the main screen (docs/design/README.md §4.1; ADR-007, ADR-011).

The two districts of T-22 are the ground: school B is «Критично» and school A is «Норма», so a
row about school A can only come from an incident or an appeal of it. The moment of the request
is pinned with ``period_to``, as in ``test_overview``: the windows of the settings are counted
back from it, and a test must not depend on when it runs.
"""

import itertools
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appeal, Line, School, SystemSettings, User
from tests.factories import bearer, create_user
from tests.test_incidents import an_incident
from tests.test_overview import WORKDAY, get, two_districts

ATTENTION = "/api/dashboard/attention"
numbers = itertools.count(1)


async def an_appeal(
    session: AsyncSession, school: School, *, author: User, sent_at: datetime
) -> Appeal:
    """Appeal of the main line of ``school``, as «Отправить» writes it (T-49, ADR-011).

    There is no factory for an appeal: the API builds one only with SMTP and a model provider
    stubbed out, and these tests need the row, not the sending.
    """
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    appeal = Appeal(
        number=f"ОБР-1999-{next(numbers):06d}",
        status="sent_to_provider",
        line_id=line.id,
        school_id=school.id,
        provider_id=line.provider_id,
        subject="Скорость ниже договорной",
        text="Просим восстановить скорость основной линии.",
        context={},
        delivery_status="sent",
        sent_at=sent_at,
        pdf=b"",
        author_user_id=author.id,
    )
    session.add(appeal)
    await session.flush()
    return appeal


async def test_a_district_sees_only_the_rows_of_its_own_schools(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    # An incident of the other district, old enough to qualify on its own.
    await an_incident(session, school_a, started_at=WORKDAY - timedelta(days=2))
    district = bearer(await create_user(session, "district", region_id=school_b.region_id))

    page = await get(api_client, ATTENTION, district)

    assert page["total"] == 1
    assert [(item["kind"], item["school_id"]) for item in page["items"]] == [
        ("school", school_b.id)
    ]
    row = page["items"][0]
    assert (row["reason"], row["status"], row["severity"]) == ("critical", "critical", 2)
    assert (row["region_name"], row["provider_name"]) == (
        "Район VKO-B-001",
        "Провайдер VKO-B-001",
    )


async def test_the_worst_row_comes_first_whatever_its_age(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Sorted by severity first and by age second (docs/design/README.md §4.1).

    The appeal is the oldest row and the critical school the newest, so an order by age alone
    would turn the list upside down. ``total`` counts the rows before ``limit``, for «Ещё N школ».
    """
    school_a, school_b = await two_districts(session)
    oblast_user = await create_user(session, "oblast")
    oblast = bearer(oblast_user)
    incident = await an_incident(session, school_a, started_at=WORKDAY - timedelta(days=2))
    appeal = await an_appeal(
        session, school_a, author=oblast_user, sent_at=WORKDAY - timedelta(days=3)
    )

    page = await get(api_client, ATTENTION, oblast)
    cut = await get(api_client, ATTENTION, oblast, limit=1)

    assert [(item["kind"], item["severity"]) for item in page["items"]] == [
        ("school", 2),
        ("incident", 3),
        ("appeal", 4),
    ]
    school, opened, letter = page["items"]
    assert (school["school_id"], school["reason"]) == (school_b.id, "critical")
    assert (opened["incident_id"], opened["incident_number"]) == (incident.id, incident.number)
    assert (opened["reason"], opened["metric"], opened["status"]) == (
        "incident_unassigned",
        "download_mbps",
        None,
    )
    assert (letter["appeal_id"], letter["appeal_number"]) == (appeal.id, appeal.number)
    assert letter["reason"] == "appeal_unanswered"
    assert (page["total"], cut["total"], len(cut["items"])) == (3, 3, 1)


async def test_the_unassigned_window_comes_from_the_settings(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """The window is a setting, not a constant of the code (ТЗ п. 11, п. 20; ADR-004).

    An incident opened 30 h ago and still without a responsible person asks for one by the
    default 24 h and stops asking as soon as an administrator gives the districts two days.
    """
    school_a, _ = await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))
    await an_incident(session, school_a, started_at=WORKDAY - timedelta(hours=30))

    qualified = await get(api_client, ATTENTION, oblast)
    settings = await session.get(SystemSettings, 1)
    assert settings is not None
    settings.attention_incident_unassigned_hours = 48
    await session.flush()
    raised = await get(api_client, ATTENTION, oblast)

    # The critical school of the other district stays either way: only the incident moves.
    assert [item["kind"] for item in qualified["items"]] == ["school", "incident"]
    assert [item["kind"] for item in raised["items"]] == ["school"]
    assert (qualified["total"], raised["total"]) == (2, 1)


async def test_the_no_answer_window_comes_from_the_settings(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """The window is a setting, not a constant of the code (ТЗ п. 11, п. 20; ADR-004).

    An appeal sent 60 h ago is «без ответа» by the default 48 h and stops being one as soon as
    an administrator gives the providers 72 h.
    """
    school_a, _ = await two_districts(session)
    oblast_user = await create_user(session, "oblast")
    oblast = bearer(oblast_user)
    await an_appeal(session, school_a, author=oblast_user, sent_at=WORKDAY - timedelta(hours=60))

    qualified = await get(api_client, ATTENTION, oblast)
    settings = await session.get(SystemSettings, 1)
    assert settings is not None
    settings.attention_appeal_no_answer_hours = 72
    await session.flush()
    raised = await get(api_client, ATTENTION, oblast)

    # The critical school of the other district stays either way: only the appeal moves.
    assert [item["kind"] for item in qualified["items"]] == ["school", "appeal"]
    assert [item["kind"] for item in raised["items"]] == ["school"]
    assert (qualified["total"], raised["total"]) == (2, 1)
