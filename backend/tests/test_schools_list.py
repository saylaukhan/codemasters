"""T-24: the school list — averages, sorting by any column and by status, scope (ADR-008)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line
from tests.factories import bearer, create_user
from tests.test_overview import get, two_districts


async def test_the_list_carries_averages_and_status_and_sorts_on_the_server(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    page = await get(api_client, "/api/schools", oblast)
    worst_first = await get(api_client, "/api/schools", oblast, sort="-status")
    slowest_first = await get(api_client, "/api/schools", oblast, sort="avg_download_mbps")
    critical = await get(api_client, "/api/schools", oblast, status="critical")
    second = await get(api_client, "/api/schools", oblast, page=2, page_size=1)

    assert (page["total"], page["page"]) == (2, 1)
    by_code = {item["school_code"]: item for item in page["items"]}
    school_a = by_code["VKO-A-001"]
    assert school_a["status"] == "normal"
    assert school_a["devices_count"] == 1
    assert school_a["avg_download_mbps"] == (90 + 60 + 30) / 3
    assert school_a["avg_ping_ms"] == 20
    assert school_a["last_measured_at"] is not None
    assert [i["school_code"] for i in worst_first["items"]] == ["VKO-B-001", "VKO-A-001"]
    assert [i["school_code"] for i in slowest_first["items"]] == ["VKO-B-001", "VKO-A-001"]
    assert [i["school_code"] for i in critical["items"]] == ["VKO-B-001"]
    assert (second["total"], len(second["items"])) == (2, 1)


async def test_a_district_and_a_provider_see_only_their_schools(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    provider_b = await session.scalar(select(Line.provider_id).where(Line.school_id == school_b.id))
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))
    provider = bearer(await create_user(session, "provider", provider_id=provider_b))

    seen_by_district = await get(api_client, "/api/schools", district)
    seen_by_provider = await get(api_client, "/api/schools", provider)

    assert [i["school_code"] for i in seen_by_district["items"]] == ["VKO-A-001"]
    assert [i["school_code"] for i in seen_by_provider["items"]] == ["VKO-B-001"]
