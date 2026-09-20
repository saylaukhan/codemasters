"""T-45: incidents in the analytics — count, length, repeatability, scope (ТЗ п. 19; ADR-008).

The two districts of ``test_overview`` with incidents put straight into the database, as the
detection of T-40 leaves them: length is ``restored_at − started_at``, so an open incident
counts but lengthens nothing, and one that started before the period does not count at all.
"""

from datetime import timedelta

from httpx import AsyncClient
from pytest import approx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line
from tests.factories import bearer, create_user
from tests.test_incidents import an_incident
from tests.test_overview import WORKDAY, get, two_districts

INCIDENT_ANALYTICS = "/api/analytics/incidents"
# One day up to the moment of the request: everything in the period is a day of WORKDAY.
DAY = {"period": "custom", "period_from": (WORKDAY - timedelta(days=1)).isoformat()}
HOUR = timedelta(hours=1)


async def test_a_school_row_counts_incidents_their_length_and_repeatability(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    # Four hours, two hours, still open, and one that started before the period.
    await an_incident(
        session,
        school_a,
        status="resolved",
        started_at=WORKDAY - 10 * HOUR,
        restored_at=WORKDAY - 6 * HOUR,
    )
    await an_incident(
        session,
        school_a,
        status="closed",
        started_at=WORKDAY - 5 * HOUR,
        restored_at=WORKDAY - 3 * HOUR,
    )
    await an_incident(session, school_a, started_at=WORKDAY - 2 * HOUR)
    await an_incident(
        session,
        school_a,
        status="closed",
        started_at=WORKDAY - 30 * HOUR,
        restored_at=WORKDAY - 29 * HOUR,
    )
    oblast = bearer(await create_user(session, "oblast"))

    report = await get(
        api_client, INCIDENT_ANALYTICS, oblast, level="school", school_id=school_a.id, **DAY
    )

    assert report["repeatability_window_days"] == 30
    [row] = report["rows"]
    assert (row["id"], row["name"]) == (school_a.id, "Школа VKO-A-001")
    assert (row["incidents_count"], row["open_count"], row["restored_count"]) == (3, 1, 2)
    # Only the two restored ones have a length: 4 h and 2 h.
    assert (row["total_duration_s"], row["avg_duration_s"], row["max_duration_s"]) == (
        6 * 3600,
        3 * 3600,
        4 * 3600,
    )
    # One main line, three incidents in a day of the period: thirty times as many in 30 days.
    assert (row["lines_count"], row["incidents_per_line_30d"]) == (1, approx(90.0))


async def test_a_school_without_incidents_keeps_its_row_with_zeros(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    report = await get(api_client, INCIDENT_ANALYTICS, oblast, level="school", **DAY)

    assert [row["name"] for row in report["rows"]] == ["Школа VKO-A-001", "Школа VKO-B-001"]
    for row in report["rows"]:
        assert (row["incidents_count"], row["open_count"], row["restored_count"]) == (0, 0, 0)
        assert row["total_duration_s"] is None
        assert row["avg_duration_s"] is None
        assert row["max_duration_s"] is None
        assert row["incidents_per_line_30d"] == 0


async def test_a_provider_counts_only_the_incidents_of_its_own_lines(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    await an_incident(session, school_a, started_at=WORKDAY - 4 * HOUR)
    await an_incident(
        session,
        school_b,
        status="resolved",
        started_at=WORKDAY - 3 * HOUR,
        restored_at=WORKDAY - 2 * HOUR,
    )
    provider_b = await session.scalar(select(Line.provider_id).where(Line.school_id == school_b.id))
    provider = bearer(await create_user(session, "provider", provider_id=provider_b))

    by_school = await get(api_client, INCIDENT_ANALYTICS, provider, level="school", **DAY)
    whole = await get(api_client, INCIDENT_ANALYTICS, provider, level="region", **DAY)

    assert [(row["name"], row["incidents_count"]) for row in by_school["rows"]] == [
        ("Школа VKO-B-001", 1)
    ]
    [oblast_row] = whole["rows"]
    assert (oblast_row["id"], oblast_row["name"]) == (None, None)
    assert (oblast_row["incidents_count"], oblast_row["lines_count"]) == (1, 1)
    assert oblast_row["total_duration_s"] == 3600


async def test_a_district_row_sums_the_incidents_of_its_schools(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    await an_incident(
        session,
        school_a,
        status="closed",
        started_at=WORKDAY - 4 * HOUR,
        restored_at=WORKDAY - 3 * HOUR,
    )
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    report = await get(api_client, INCIDENT_ANALYTICS, district, level="district", **DAY)

    [row] = report["rows"]
    assert (row["id"], row["incidents_count"], row["avg_duration_s"]) == (
        school_a.region_id,
        1,
        3600,
    )
