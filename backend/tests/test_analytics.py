"""T-27: analytics from the aggregates — rows of a level, series, heatmap, scope (ADR-008).

The two districts of ``test_overview``: school A measured 90, 60 and 30 Mbit/s (one of them
critical), school B 10 and 20, all on Friday before 14:00 Asia/Almaty.
"""

from datetime import timedelta

from httpx import AsyncClient
from pytest import approx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line
from tests.factories import bearer, create_settings, create_user
from tests.test_overview import WORKDAY, get, two_districts

DAY = {"period": "custom", "period_from": (WORKDAY - timedelta(days=1)).isoformat()}


async def test_the_school_card_gets_its_numbers_series_and_heatmap(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    report = await get(
        api_client, "/api/analytics", oblast, level="school", school_id=school_a.id, **DAY
    )

    assert report["granularity"] == "day"
    [row] = report["rows"]
    assert (row["id"], row["measurements_count"], row["problem_count"]) == (school_a.id, 3, 1)
    assert row["problem_pct"] == approx(100 / 3)
    assert row["download_mbps"] == {"avg": 60.0, "min": 30.0, "max": 90.0}
    assert row["ping_ms"] == {"avg": 20.0, "min": 20.0, "max": 20.0}
    # No contract speeds on the line: nothing to compare with.
    assert row["below_contract_pct"] is None
    # Working time Thu 14:00–18:00 and Fri 08:00–14:00; one heartbeat vouches for 13:59–14:00.
    assert row["availability_pct"] == approx(100 / 600)
    [point] = report["series"]
    assert (point["measurements_count"], point["avg_download_mbps"]) == (3, 60.0)
    assert [(cell["weekday"], cell["hour"]) for cell in report["heatmap"]] == [
        ("fri", 11),
        ("fri", 12),
        ("fri", 13),
    ]
    assert report["thresholds"]["download_min_mbps"] >= 0
    assert report["availability_min_pct"] == 99


async def test_a_provider_sees_only_its_lines_on_every_level(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, school_b = await two_districts(session)
    provider_b = await session.scalar(select(Line.provider_id).where(Line.school_id == school_b.id))
    provider = bearer(await create_user(session, "provider", provider_id=provider_b))

    by_provider = await get(api_client, "/api/analytics", provider, level="provider", **DAY)
    by_school = await get(api_client, "/api/analytics", provider, level="school", **DAY)
    whole = await get(api_client, "/api/analytics", provider, level="region", **DAY)

    assert [row["id"] for row in by_provider["rows"]] == [provider_b]
    assert [row["name"] for row in by_school["rows"]] == ["Школа VKO-B-001"]
    assert whole["rows"][0]["measurements_count"] == 2
    assert whole["rows"][0]["download_mbps"]["max"] == 20.0


async def test_bounds_come_only_with_a_custom_period(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    oblast = bearer(await create_user(session, "oblast"))

    preset = await api_client.get(
        "/api/analytics",
        headers=oblast,
        params={"level": "region", "period": "week", "period_to": WORKDAY.isoformat()},
    )
    custom = await api_client.get(
        "/api/analytics", headers=oblast, params={"level": "region", "period": "custom"}
    )

    assert preset.status_code == custom.status_code == 422
    assert preset.json()["errors"][0]["field"] == "period_to"
    assert custom.json()["errors"][0]["field"] == "period_from"
