"""T-31: aggregates per school — one row per school, the numbers of the analytics (T-27).

The two districts of ``test_overview``: school A measured 90, 60 and 30 Mbit/s (one of them
critical), school B 10 and 20 (both critical), all on Friday before 14:00 Asia/Almaty.
"""

import csv
import io
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from pytest import approx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line
from tests.factories import bearer, create_user
from tests.test_exports import download, xlsx_rows
from tests.test_overview import WORKDAY, get, measured, two_districts

PERIOD_FROM = WORKDAY - timedelta(days=1)
HEADER = [
    "School ID",
    "Школа",
    "Замеров",
    "Средний Download, Мбит/с",
    "Минимальный Download, Мбит/с",
    "Средний Upload, Мбит/с",
    "Средний Ping, мс",
    "Проблемных замеров",
    "Доля проблемных, %",
]


async def aggregates(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Any:
    body = {
        "mode": "aggregates",
        "format": "json",
        "period_from": PERIOD_FROM.isoformat(),
        "period_to": WORKDAY.isoformat(),
    } | changes
    created = await client.post("/api/exports", json=body, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


async def test_the_problem_share_is_the_one_of_the_analytics(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    # Wi-Fi measures the air, not the line: in neither the analytics nor the export (ADR-012).
    device = await session.scalar(select(Device).where(Device.device_uid == "VKO-A-001"))
    line_id = await session.scalar(select(Line.id).where(Line.school_id == school_a.id))
    assert device is not None
    assert line_id is not None
    await measured(
        session, device, line_id, hours_ago=5, status="critical", download=1, iface_type="wifi"
    )
    oblast = bearer(await create_user(session, "oblast"))

    job = await aggregates(api_client, oblast)
    records = (await download(api_client, oblast, job["id"])).json()
    report = await get(
        api_client,
        "/api/analytics",
        oblast,
        level="school",
        period="custom",
        period_from=PERIOD_FROM.isoformat(),
    )

    assert job["rows_count"] == 2
    assert records[0] == {
        "school_code": "VKO-A-001",
        "school_name": "Школа VKO-A-001",
        "measurements_count": 3,
        "avg_download_mbps": 60.0,
        "min_download_mbps": 30.0,
        "avg_upload_mbps": 30.0,
        "avg_ping_ms": 20.0,
        "problem_count": 1,
        "problem_pct": 33.33,
    }
    rows = {row["id"]: row for row in report["rows"]}
    for school, record in zip([school_a, school_b], records, strict=True):
        row = rows[school.id]
        assert record["school_name"] == row["name"]
        assert (record["measurements_count"], record["problem_count"]) == (
            row["measurements_count"],
            row["problem_count"],
        )
        assert record["problem_pct"] == approx(row["problem_pct"], abs=0.005)
        assert record["avg_download_mbps"] == approx(row["download_mbps"]["avg"], abs=0.005)
        assert record["min_download_mbps"] == row["download_mbps"]["min"]
    assert records[1]["problem_pct"] == 100.0


async def test_xlsx_and_csv_have_one_row_per_school_with_the_columns_of_tz_p9(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    xlsx_job = await aggregates(api_client, oblast, format="xlsx")
    csv_job = await aggregates(api_client, oblast, format="csv")
    xlsx_file = await download(api_client, oblast, xlsx_job["id"])
    csv_file = (await download(api_client, oblast, csv_job["id"])).content

    assert xlsx_file.headers["content-disposition"] == (
        'attachment; filename="schools_2026-09-17_2026-09-18.xlsx"'
    )
    rows = xlsx_rows(xlsx_file.content)
    assert rows[0] == HEADER
    assert rows[1] == [
        "VKO-A-001",
        "Школа VKO-A-001",
        "3",
        "60.0",
        "30.0",
        "30.0",
        "20.0",
        "1",
        "33.33",
    ]
    assert len(rows) == 3
    csv_rows = list(csv.reader(io.StringIO(csv_file.decode("utf-8-sig")), delimiter=";"))
    assert csv_rows[0] == HEADER
    assert csv_rows[1][-2:] == ["1", "33,33"]
    assert csv_rows[2] == [
        "VKO-B-001",
        "Школа VKO-B-001",
        "2",
        "15,0",
        "10,0",
        "7,5",
        "20,0",
        "2",
        "100,0",
    ]


async def test_a_district_gets_only_its_schools_and_raw_only_filters_are_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    job = await aggregates(api_client, district)
    foreign = await api_client.post(
        "/api/exports",
        json={
            "mode": "aggregates",
            "format": "json",
            "period_from": PERIOD_FROM.isoformat(),
            "period_to": WORKDAY.isoformat(),
            "school_ids": [school_b.id],
        },
        headers=district,
    )
    with_statuses = await api_client.post(
        "/api/exports",
        json={
            "mode": "aggregates",
            "format": "json",
            "period_from": PERIOD_FROM.isoformat(),
            "period_to": WORKDAY.isoformat(),
            "statuses": ["critical"],
        },
        headers=district,
    )

    records = (await download(api_client, district, job["id"])).json()
    assert [record["school_code"] for record in records] == ["VKO-A-001"]
    assert foreign.status_code == with_statuses.status_code == 422
