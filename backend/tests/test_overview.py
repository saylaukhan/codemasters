"""T-22: the KPIs of the overview and the schools on the map (ТЗ п. 4, п. 13; ADR-004, ADR-008).

Two districts, A and B, one school in each, with a computer that is alive and a few evaluated
measurements. The moment of the request is fixed with ``period_to``: the status of a school
depends on the working hours (ADR-014), and a test must not depend on when it runs.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from geoalchemy2 import WKTElement
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Heartbeat, Line, Measurement, Region, School
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

# Friday 14:00 Asia/Almaty: inside the default working hours 08:00–18:00, Mon–Sat.
WORKDAY = datetime(2026, 9, 18, 14, 0, tzinfo=ZoneInfo("Asia/Almaty"))
AT_WORKDAY = {"period_to": WORKDAY.isoformat()}
SNAPSHOT = {"download_min_mbps": 50.0, "upload_min_mbps": 20.0, "ping_max_ms": 100.0}


async def school_with_series(
    session: AsyncSession, code: str, series: list[tuple[str, float]], *, lon: float
) -> School:
    """School of its own district with an alive computer and measurements of its main line,
    newest first: (quality status, download)."""
    school = await create_school(session, school_code=code)
    school.geom = WKTElement(f"POINT({lon} 49.95)", srid=4326)
    device, _ = await register_device(
        session, await primary_point(session, school), device_uid=code
    )
    await alive(session, device)
    line_id = await session.scalar(select(Line.id).where(Line.school_id == school.id))
    assert line_id is not None
    for age, (quality_status, download) in enumerate(series):
        await measured(
            session, device, line_id, hours_ago=age + 1, status=quality_status, download=download
        )
    return school


async def alive(session: AsyncSession, device: Device) -> None:
    moment = WORKDAY - timedelta(minutes=1)
    device.last_seen_at = moment
    session.add(Heartbeat(device_id=device.id, ts=moment, online=True))
    await session.flush()


async def measured(
    session: AsyncSession,
    device: Device,
    line_id: int,
    *,
    hours_ago: float,
    status: str,
    download: float,
    iface_type: str = "ethernet",
) -> None:
    session.add(
        Measurement(
            measurement_uuid=uuid.uuid4(),
            measured_at=WORKDAY - timedelta(hours=hours_ago),
            device_id=device.id,
            line_id=line_id,
            connection_status="online",
            iface_type=iface_type,
            download_mbps=download,
            upload_mbps=download / 2,
            ping_ms=20.0,
            quality_status=status,
            thresholds_snapshot=SNAPSHOT,
        )
    )
    await session.flush()


async def two_districts(session: AsyncSession) -> tuple[School, School]:
    await create_settings(session)
    school_a = await school_with_series(
        session, "VKO-A-001", [("normal", 90.0), ("normal", 60.0), ("critical", 30.0)], lon=82.6
    )
    school_b = await school_with_series(
        session, "VKO-B-001", [("critical", 10.0), ("critical", 20.0)], lon=82.7
    )
    return school_a, school_b


async def get(client: AsyncClient, path: str, user_headers: dict[str, str], **params: Any) -> Any:
    response = await client.get(path, headers=user_headers, params={**AT_WORKDAY, **params})
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_district_sees_only_its_schools_on_the_map_and_in_the_kpis(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    schools = await get(api_client, "/api/map/schools", district)
    summary = await get(api_client, "/api/dashboard/summary", district)
    options = await get(api_client, "/api/map/filters", district)
    # Asking for the other district by its id gives nothing, not its schools.
    stranger = await get(api_client, "/api/map/schools", district, region_id=school_b.region_id)

    assert [feature["properties"]["school_code"] for feature in schools["features"]] == [
        "VKO-A-001"
    ]
    assert (summary["schools_count"], summary["devices_count"]) == (1, 1)
    assert [region["name"] for region in options["regions"]] == ["Район VKO-A-001"]
    assert [provider["name"] for provider in options["providers"]] == ["Провайдер VKO-A-001"]
    assert stranger["features"] == []


async def test_the_map_carries_the_status_and_the_last_measurement_of_the_main_line(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    schools = await get(api_client, "/api/map/schools", oblast)
    critical = await get(api_client, "/api/map/schools", oblast, status=["critical", "offline"])

    by_code = {f["properties"]["school_code"]: f for f in schools["features"]}
    feature = by_code["VKO-A-001"]
    assert feature["id"] == school_a.id
    assert feature["geometry"] == {"type": "Point", "coordinates": [82.6, 49.95]}
    properties = feature["properties"]
    # Two of the last three are normal: the older critical one does not colour the school.
    assert properties["status"] == "normal"
    assert (properties["download_mbps"], properties["download_min_mbps"]) == (90.0, 50.0)
    assert properties["provider_name"] == "Провайдер VKO-A-001"
    assert by_code["VKO-B-001"]["properties"]["status"] == "critical"
    assert [f["id"] for f in critical["features"]] == [school_b.id]


async def test_the_kpis_count_main_line_measurements_without_wifi(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_districts(session)
    device = (await session.scalars(select(Device).where(Device.device_uid == "VKO-A-001"))).one()
    line_id = await session.scalar(select(Line.id).where(Line.school_id == school_a.id))
    assert line_id is not None
    # The newest measurement of school A is over Wi-Fi: it measures the air, not the line.
    await measured(
        session, device, line_id, hours_ago=0.5, status="critical", download=1.0, iface_type="wifi"
    )
    oblast = bearer(await create_user(session, "oblast"))

    summary = await get(api_client, "/api/dashboard/summary", oblast)
    only_b = await get(api_client, "/api/dashboard/summary", oblast, status="critical")
    old = await get(
        api_client,
        "/api/dashboard/summary",
        oblast,
        period_from=(WORKDAY - timedelta(hours=10)).isoformat(),
        period_to=(WORKDAY - timedelta(hours=5)).isoformat(),
    )

    assert summary["schools_count"] == 2
    assert (summary["devices_count"], summary["active_devices_count"]) == (2, 2)
    assert summary["measurements_count"] == 5
    assert summary["avg_download_mbps"] == (90 + 60 + 30 + 10 + 20) / 5
    assert summary["avg_ping_ms"] == 20
    # PC of school B ended on a critical measurement; the Wi-Fi one of school A is not counted.
    assert summary["problem_devices_count"] == 1
    assert (only_b["schools_count"], only_b["measurements_count"]) == (1, 2)
    # Nothing was measured or heard in that window, so there is nothing to average.
    assert (old["measurements_count"], old["active_devices_count"]) == (0, 0)
    assert old["avg_download_mbps"] is None


async def test_region_boundaries_are_geojson_for_every_role(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_districts(session)
    region = await session.get(Region, school_a.region_id)
    assert region is not None
    region.geom = WKTElement(
        "MULTIPOLYGON(((82.5 49.9, 82.7 49.9, 82.7 50.0, 82.5 49.9)))", srid=4326
    )
    await session.flush()
    school_user = bearer(await create_user(session, "school", school_id=school_b.id))

    regions = await get(api_client, "/api/map/regions", school_user)

    by_name = {f["properties"]["name"]: f for f in regions["features"]}
    assert by_name["Район VKO-A-001"]["geometry"]["type"] == "MultiPolygon"
    assert by_name["Район VKO-B-001"]["geometry"] is None
