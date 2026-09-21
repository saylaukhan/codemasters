"""T-17: configuration of an agent — schedule, thresholds, servers, version (ADR-004, ADR-012).

Nothing of it is built into the agent: every value comes from the database along the chain
device → line → district → global settings, and the ETag lets an unchanged configuration cost
one 304 (ТЗ п. 11, п. 20).
"""

from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PROBLEM_MEDIA_TYPE
from app.models import AgentRelease, Line, Schedule, School, ThresholdProfile
from tests.factories import create_school, create_settings, primary_point, register_device

CONFIG = "/api/agent/config"
WHOAMI = "/api/agent/whoami"

# Four slots and base thresholds of «Решения по умолчанию», created by the migration of T-17.
DEFAULT_SLOTS = [
    {"start": "08:30:00", "end": "09:00:00"},
    {"start": "11:00:00", "end": "11:30:00"},
    {"start": "13:30:00", "end": "14:00:00"},
    {"start": "16:00:00", "end": "16:30:00"},
]
DEFAULT_THRESHOLDS = {
    "download_min_mbps": 20.0,
    "upload_min_mbps": 20.0,
    "ping_max_ms": 100.0,
    "jitter_max_ms": 30.0,
    "packet_loss_max_pct": 2.0,
}
NIGHT_SLOTS = [
    {"start": "20:00:00", "end": "20:30:00"},
    {"start": "21:00:00", "end": "21:30:00"},
    {"start": "22:00:00", "end": "22:30:00"},
]


def as_device(token: str) -> dict[str, str]:
    return {"Authorization": f"Device {token}"}


async def device_of_a_school(session: AsyncSession, **school: Any) -> tuple[School, str]:
    """School with settings, one device on its primary point and the token of that device."""
    created = await create_school(session, **school)
    await create_settings(session)
    _, token = await register_device(session, await primary_point(session, created))
    return created, token


async def global_schedule(session: AsyncSession) -> Schedule:
    return (await session.scalars(select(Schedule).where(Schedule.scope == "global"))).one()


async def line_of(session: AsyncSession, school: School) -> Line:
    return (await session.scalars(select(Line).where(Line.school_id == school.id))).one()


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


async def test_config_carries_the_schedule_thresholds_and_servers(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    await create_settings(session, librespeed_url="https://speedtest.example.kz", ndt7_url="ws://n")
    _, token = await register_device(session, await primary_point(session, school))

    response = await api_client.get(CONFIG, headers=as_device(token))

    assert response.status_code == 200, response.text
    body = response.json()
    # The slots and the thresholds of «Решения по умолчанию» и ТЗ п. 11 come from the database.
    assert body["schedule_slots"] == DEFAULT_SLOTS
    assert body["thresholds"] == DEFAULT_THRESHOLDS
    assert body["timezone"] == "Asia/Almaty"
    assert body["speedtest"] == {
        "librespeed_url": "https://speedtest.example.kz",
        "ndt7_url": "ws://n",
    }
    assert (body["heartbeat_interval_s"], body["config_refresh_interval_s"]) == (300, 900)
    # Срок очереди тоже приходит с сервера: в агенте его нет (ADR-006).
    assert body["queue_retention_days"] == 30
    # No release is published yet, so the agent is not asked to update (T-50).
    assert body["latest_version"] is None
    assert response.headers["etag"].startswith('"')


async def test_unchanged_config_answers_304_and_a_changed_schedule_does_not(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token = await device_of_a_school(session)

    first = await api_client.get(CONFIG, headers=as_device(token))
    etag = first.headers["etag"]
    repeated = await api_client.get(CONFIG, headers=as_device(token) | {"If-None-Match": etag})
    schedule = await global_schedule(session)
    schedule.slots = NIGHT_SLOTS
    await session.flush()
    changed = await api_client.get(CONFIG, headers=as_device(token) | {"If-None-Match": etag})

    assert repeated.status_code == 304
    assert repeated.content == b""
    assert repeated.headers["etag"] == etag
    # A row of ``schedules`` changed: the answer and its version change with it.
    assert changed.status_code == 200, changed.text
    assert changed.json()["schedule_slots"] == NIGHT_SLOTS
    assert changed.headers["etag"] != etag


async def test_the_most_specific_schedule_and_profile_win(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school, token = await device_of_a_school(session)
    line = await line_of(session, school)
    district = Schedule(scope="district", region_id=school.region_id, slots=NIGHT_SLOTS)
    strict = ThresholdProfile(
        scope="district",
        region_id=school.region_id,
        download_min_mbps=50,
        upload_min_mbps=50,
        ping_max_ms=40,
        jitter_max_ms=10,
        packet_loss_max_pct=1,
        unstable_deviation_pct=20,
    )
    session.add_all([district, strict])
    await session.flush()

    by_district = (await api_client.get(CONFIG, headers=as_device(token))).json()
    own = Schedule(scope="school", school_id=school.id, slots=DEFAULT_SLOTS)
    for_the_line = ThresholdProfile(
        scope="line",
        line_id=line.id,
        download_min_mbps=5,
        upload_min_mbps=5,
        ping_max_ms=300,
        jitter_max_ms=90,
        packet_loss_max_pct=10,
        unstable_deviation_pct=50,
    )
    session.add_all([own, for_the_line])
    await session.flush()
    by_school = (await api_client.get(CONFIG, headers=as_device(token))).json()
    own.is_active = False
    for_the_line.is_active = False
    await session.flush()
    switched_off = (await api_client.get(CONFIG, headers=as_device(token))).json()

    # District beats global, the school and its own line beat the district.
    assert by_district["schedule_slots"] == NIGHT_SLOTS
    assert by_district["thresholds"]["download_min_mbps"] == 50
    assert by_school["schedule_slots"] == DEFAULT_SLOTS
    assert by_school["thresholds"]["download_min_mbps"] == 5
    # A switched-off row is skipped and the next one of the chain applies again.
    assert switched_off["schedule_slots"] == NIGHT_SLOTS
    assert switched_off["thresholds"]["download_min_mbps"] == 50


async def test_latest_version_is_the_newest_active_release_of_the_stable_channel(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token = await device_of_a_school(session)
    session.add_all(
        [
            AgentRelease(version="0.2.0", channel="stable", download_url="u", sha256="a" * 64),
            AgentRelease(version="0.3.0", channel="pilot", download_url="u", sha256="b" * 64),
            AgentRelease(
                version="0.2.1",
                channel="stable",
                download_url="u",
                sha256="c" * 64,
                is_active=False,
            ),
        ]
    )
    await session.flush()

    body = (await api_client.get(CONFIG, headers=as_device(token))).json()

    # A pilot release and a withdrawn one are not offered to an agent of the stable channel.
    assert body["latest_version"] == "0.2.0"


async def test_config_without_settings_is_service_unavailable(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    _, token = await register_device(session, await primary_point(session, school))

    response = await api_client.get(CONFIG, headers=as_device(token))

    problem(response, 503, "not_configured")


async def test_whoami_returns_the_address_the_proxy_saw(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    _, token = await device_of_a_school(session)

    direct = await api_client.get(WHOAMI, headers=as_device(token))
    proxied = await api_client.get(
        WHOAMI, headers=as_device(token) | {"X-Forwarded-For": "203.0.113.7, 198.51.100.2"}
    )

    assert direct.json() == {"external_ip": "127.0.0.1"}
    # The proxy appends the address it saw, so the last entry is the one the agent cannot forge.
    assert proxied.json() == {"external_ip": "198.51.100.2"}


async def test_agent_configuration_needs_the_device_token(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await device_of_a_school(session)

    for path in (CONFIG, WHOAMI):
        problem(await api_client.get(path), 401, "unauthorized")
