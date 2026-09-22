"""T-64: «Будет выгружено ≈ N строк» — the estimate of an export before its file is built.

The same two districts as ``test_exports_aggregates``: school A measured 90, 60 and 30 Mbit/s
(one of them critical), school B 10 and 20 (both critical), all on Friday before 14:00
Asia/Almaty, so every measurement falls into one day of ``m_daily``. The counters come from
that continuous aggregate; it is created ``materialized_only = false``, so the rows a test
inserts are read straight from the hypertable without a refresh.
"""

from datetime import datetime
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device
from tests.factories import bearer, create_user
from tests.test_exports_aggregates import PERIOD_FROM, aggregates
from tests.test_overview import WORKDAY, two_districts


def query(**changes: Any) -> dict[str, Any]:
    return {
        "mode": "raw",
        "period_from": PERIOD_FROM.isoformat(),
        "period_to": WORKDAY.isoformat(),
    } | changes


async def ask(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Response:
    return await client.get("/api/exports/estimate", params=query(**changes), headers=headers)


async def estimate(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Any:
    response = await ask(client, headers, **changes)
    assert response.status_code == 200, response.text
    return response.json()


async def raw_export(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Any:
    """The file the estimate is about: the same filters, built and counted row by row."""
    created = await client.post(
        "/api/exports", json=query(format="json", **changes), headers=headers
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_the_raw_estimate_counts_the_measurements_of_the_selection(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    device = await session.scalar(select(Device).where(Device.device_uid == "VKO-A-001"))
    assert device is not None
    oblast = bearer(await create_user(session, "oblast"))

    everything = await estimate(api_client, oblast)
    of_device = await estimate(api_client, oblast, school_ids=[school_a.id], device_ids=[device.id])
    normal = await estimate(api_client, oblast, school_ids=[school_a.id], statuses=["normal"])
    problems = await estimate(
        api_client, oblast, school_ids=[school_a.id], statuses=["critical", "offline"]
    )
    job = await raw_export(api_client, oblast)

    assert everything["mode"] == "raw"
    assert datetime.fromisoformat(everything["period_from"]) == PERIOD_FROM
    assert datetime.fromisoformat(everything["period_to"]) == WORKDAY
    # The estimate is not exact: m_daily holds no Wi-Fi and counts a touched day whole.
    assert everything["exact"] is False
    assert everything["rows_count"] == job["rows_count"] == 5
    assert of_device["rows_count"] == 3
    assert (normal["rows_count"], problems["rows_count"]) == (2, 1)


async def test_a_district_counts_only_its_schools_and_a_foreign_one_is_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    own = await estimate(api_client, district)
    foreign = await ask(api_client, district, school_ids=[school_b.id])

    assert own["rows_count"] == 3
    assert foreign.status_code == 422, foreign.text
    assert [error["field"] for error in foreign.json()["errors"]] == ["school_ids"]


async def test_the_aggregates_estimate_is_the_number_of_schools_and_is_exact(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    whole_oblast = await estimate(api_client, oblast, mode="aggregates")
    own = await estimate(api_client, district, mode="aggregates")
    job = await aggregates(api_client, oblast)

    assert whole_oblast["exact"] is True
    assert whole_oblast["rows_count"] == job["rows_count"] == 2
    assert own["rows_count"] == 1


async def test_the_raw_only_filters_and_the_pdf_report_are_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    with_statuses = await ask(api_client, oblast, mode="aggregates", statuses=["critical"])
    with_devices = await ask(api_client, oblast, mode="aggregates", device_ids=[1])
    report = await ask(api_client, oblast, mode="school_report")
    backwards = await ask(
        api_client, oblast, period_from=WORKDAY.isoformat(), period_to=PERIOD_FROM.isoformat()
    )

    assert with_statuses.status_code == with_devices.status_code == 422, with_statuses.text
    assert report.status_code == backwards.status_code == 422, report.text
    assert with_statuses.json()["type"] == "validation_error"
