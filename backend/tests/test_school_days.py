"""T-61: the day strip of the school cabinet — the status of every local day of the window.

The strip has no gaps: a day without measurements and without outages is «Нет данных», and the
window is exactly the days asked for, oldest first. Two rules are checked against the fixtures
of the aggregates (T-19) and of the availability (T-16): a day of Almaty starts at midnight of
Almaty — a measurement at 02:00 belongs to that day, not to the previous UTC one — and an
outage counts only inside the working hours of the school (ADR-014).
"""

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, Measurement, Outage, School
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

ALMATY = ZoneInfo("Asia/Almaty")

# Monday noon: the window ends inside the working hours of its last day.
PERIOD_TO = datetime(2026, 9, 21, 12, 0, tzinfo=ALMATY)

# Friday of the same week: the day the measurements and the outages of the tests are put on.
FRIDAY = date(2026, 9, 18)

DAYS_PATH = "/api/schools/{school_id}/days"


def moment(day: date, hour: int) -> datetime:
    """An hour of a local day of the school, as the agent measured it (ADR-014)."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=ALMATY)


async def measuring_school(
    session: AsyncSession, code: str = "VKO-UK-001"
) -> tuple[School, Line, Device]:
    """A school with one computer on its main line and nothing measured yet."""
    school = await create_school(session, school_code=code)
    device, _ = await register_device(
        session, await primary_point(session, school), device_uid=code
    )
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    return school, line, device


def measurement(device: Device, line: Line, at: datetime, status: str) -> Measurement:
    """One measurement of the main line with the verdict T-18 wrote on receipt (ADR-004)."""
    return Measurement(
        measurement_uuid=uuid4(),
        measured_at=at.astimezone(UTC),
        device_id=device.id,
        line_id=line.id,
        connection_status="offline" if status == "offline" else "online",
        iface_type="ethernet",
        download_mbps=None if status == "offline" else 50.0,
        quality_status=status,
    )


def outage(device: Device, line: Line, started_at: datetime, ended_at: datetime) -> Outage:
    """One episode without connection, as ``POST /api/outages`` stores it (T-16)."""
    return Outage(
        device_id=device.id,
        line_id=line.id,
        started_at=started_at.astimezone(UTC),
        ended_at=ended_at.astimezone(UTC),
    )


async def strip(
    client: AsyncClient, school_id: int, headers: dict[str, str], **query: Any
) -> dict[str, Any]:
    """The day strip of the school at ``PERIOD_TO``, so the days of a test are fixed."""
    response = await client.get(
        DAYS_PATH.format(school_id=school_id),
        headers=headers,
        params={"period_to": PERIOD_TO.isoformat(), **query},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def by_date(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Days of the strip by their local date, to name the day a test is about."""
    return {day["date"]: day for day in body["days"]}


async def test_a_day_takes_the_worst_status_of_its_measurements(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """02:00 in Almaty is 21:00 UTC of the day before and still belongs to the school day."""
    await create_settings(session)
    school, line, device = await measuring_school(session)
    session.add_all(
        [
            measurement(device, line, moment(FRIDAY, 2), "normal"),
            measurement(device, line, moment(FRIDAY, 9), "critical"),
            measurement(device, line, moment(FRIDAY, 14), "unstable"),
        ]
    )
    await session.flush()
    oblast = bearer(await create_user(session, "oblast"))

    days = by_date(await strip(api_client, school.id, oblast, days=4))

    friday = days["2026-09-18"]
    # All three are of the 18th: the night one did not fall out of the window into the 17th.
    assert (friday["status"], friday["measurements_count"]) == ("critical", 3)
    assert (friday["problem_count"], friday["downtime_s"]) == (2, 0)
    assert days["2026-09-19"]["status"] == "no_data"


async def test_an_outage_in_working_hours_makes_the_day_offline(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, line, device = await measuring_school(session)
    session.add_all(
        [
            measurement(device, line, moment(FRIDAY, 9), "normal"),
            outage(device, line, moment(FRIDAY, 10), moment(FRIDAY, 12)),
        ]
    )
    await session.flush()
    oblast = bearer(await create_user(session, "oblast"))

    days = by_date(await strip(api_client, school.id, oblast, days=4))

    friday = days["2026-09-18"]
    # The outage overrides the measurements of the day, and its two hours are the downtime.
    assert (friday["status"], friday["downtime_s"]) == ("offline", 7200)
    assert (friday["measurements_count"], friday["problem_count"]) == (1, 0)


async def test_an_outage_at_night_leaves_the_day_to_its_measurements(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """A line down while the school is closed is not a day without internet (ADR-014)."""
    await create_settings(session)
    school, line, device = await measuring_school(session)
    session.add_all(
        [
            measurement(device, line, moment(FRIDAY, 9), "normal"),
            outage(device, line, moment(FRIDAY, 22), moment(FRIDAY, 23)),
        ]
    )
    await session.flush()
    oblast = bearer(await create_user(session, "oblast"))

    days = by_date(await strip(api_client, school.id, oblast, days=4))

    friday = days["2026-09-18"]
    assert (friday["status"], friday["downtime_s"]) == ("normal", 0)


async def test_a_day_without_measurements_and_outages_has_no_data(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, _, _ = await measuring_school(session)
    oblast = bearer(await create_user(session, "oblast"))

    days = by_date(await strip(api_client, school.id, oblast, days=3))

    empty = days["2026-09-20"]
    assert (empty["status"], empty["measurements_count"]) == ("no_data", 0)
    assert (empty["problem_count"], empty["downtime_s"]) == (0, 0)


async def test_the_window_is_the_days_asked_for_oldest_first(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, _, _ = await measuring_school(session)
    oblast = bearer(await create_user(session, "oblast"))

    body = await strip(api_client, school.id, oblast, days=30)

    dates = [day["date"] for day in body["days"]]
    assert len(dates) == 30
    assert dates == sorted(dates)
    assert (dates[0], dates[-1]) == ("2026-08-23", "2026-09-21")
    # The window starts at midnight of its first day in Almaty and ends at the moment asked for.
    assert body["period_from"] == "2026-08-22T19:00:00Z"
    assert body["period_to"] == "2026-09-21T07:00:00Z"
    assert body["school_id"] == school.id


async def test_the_window_is_at_most_ninety_days(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, _, _ = await measuring_school(session)
    oblast = bearer(await create_user(session, "oblast"))

    response = await api_client.get(
        DAYS_PATH.format(school_id=school.id), headers=oblast, params={"days": 91}
    )

    assert response.status_code == 422, response.text
    assert response.json()["errors"] == [
        {"field": "days", "message": "Значение должно быть не больше 90"}
    ]


async def test_a_foreign_school_is_not_found_for_a_school_user(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    own, _, _ = await measuring_school(session, "VKO-A-001")
    other, _, _ = await measuring_school(session, "VKO-B-001")
    headers = bearer(await create_user(session, "school", school_id=own.id))

    foreign = await api_client.get(DAYS_PATH.format(school_id=other.id), headers=headers)
    mine = await api_client.get(DAYS_PATH.format(school_id=own.id), headers=headers)

    assert foreign.status_code == 404, foreign.text
    assert foreign.json()["type"] == "not_found"
    assert mine.status_code == 200, mine.text
    assert len(mine.json()["days"]) == 30
