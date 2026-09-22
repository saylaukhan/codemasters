"""T-69: «Внедрение» — who is not connected, who is silent, which agents are behind (§6.4).

The share of connected schools of a district has to agree with the main screen, so one test
asks both endpoints and compares their answers instead of repeating the definition. The moment
of a request is pinned with ``as_of`` and the windows are counted back from it: a test must not
depend on when it runs (as in ``test_overview``).
"""

from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRelease, EnrollmentCode, Heartbeat, School, SystemSettings
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    issue_enrollment_code,
    primary_point,
    register_device,
)
from tests.test_overview import WORKDAY, two_districts

SUMMARY = "/api/rollout/summary"
SCHOOLS = "/api/rollout/schools"
ASSIGN = "/api/rollout/devices/agent-update"
DASHBOARD = "/api/dashboard/summary"

# Version of the stable release the fixture publishes, and the one left behind by it.
CURRENT = "0.2.0"
BEHIND = "0.1.0"
# A signal a minute old is «на связи» by the default ``offline_after_s`` of 900 s.
ALIVE = timedelta(minutes=1)
# Silence of nine days is «молчит» by the default ``rollout_silent_days`` of 7.
SILENCE = timedelta(days=9)


async def get(client: AsyncClient, path: str, headers: dict[str, str], **params: Any) -> Any:
    params = {"as_of": WORKDAY.isoformat(), **params}
    response = await client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def a_release(
    session: AsyncSession,
    version: str = CURRENT,
    *,
    channel: str = "stable",
    released_ago: timedelta = timedelta(days=30),
) -> AgentRelease:
    """Active release; everything older than the stable one is «старая версия» (T-50)."""
    release = AgentRelease(
        version=version,
        channel=channel,
        download_url=f"https://monitor.example.kz/downloads/VKO-Agent-{version}.msi",
        sha256="a" * 64,
        released_at=WORKDAY - released_ago,
    )
    session.add(release)
    await session.flush()
    return release


async def connected_school(
    session: AsyncSession, code: str, *, version: str, seen_ago: timedelta
) -> School:
    """School with one active computer last heard ``seen_ago`` before the pinned moment."""
    school = await create_school(session, school_code=code)
    device, _ = await register_device(
        session, await primary_point(session, school), device_uid=code
    )
    device.agent_version = version
    moment = WORKDAY - seen_ago
    device.last_seen_at = moment
    session.add(Heartbeat(device_id=device.id, ts=moment, online=True))
    await session.flush()
    return school


async def unused_code(session: AsyncSession, school: School, *, issued_ago: timedelta) -> None:
    """Installation code of the school, issued ``issued_ago`` ago and never used (T-36)."""
    await issue_enrollment_code(session, school)
    code = (
        await session.scalars(select(EnrollmentCode).where(EnrollmentCode.school_id == school.id))
    ).one()
    code.created_at = WORKDAY - issued_ago
    await session.flush()


async def one_of_each(session: AsyncSession) -> dict[str, School]:
    """Four schools, one per list of §6.4, so every list must pick exactly its own."""
    await create_settings(session)
    await a_release(session)
    return {
        # A school with a point but no computer at all.
        "not_connected": await create_school(session, school_code="VKO-NC-001"),
        "silent": await connected_school(session, "VKO-SI-001", version=CURRENT, seen_ago=SILENCE),
        "code_unused": await code_issued(session),
        "old_version": await connected_school(
            session, "VKO-OV-001", version=BEHIND, seen_ago=ALIVE
        ),
    }


async def code_issued(session: AsyncSession) -> School:
    """Connected school on the current version whose second computer was never installed."""
    school = await connected_school(session, "VKO-CU-001", version=CURRENT, seen_ago=ALIVE)
    await unused_code(session, school, issued_ago=SILENCE)
    return school


async def test_a_district_counts_only_its_own_schools(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Scope of ADR-008: the other district is neither in the numbers nor in the districts."""
    school_a, school_b = await two_districts(session)
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    summary = await get(api_client, SUMMARY, district)
    stranger = await get(api_client, SUMMARY, district, region_id=school_b.region_id)

    assert (summary["schools_count"], summary["schools_connected_count"]) == (1, 1)
    assert [row["region_name"] for row in summary["regions"]] == ["Район VKO-A-001"]
    assert (stranger["schools_count"], stranger["regions"]) == (0, [])


async def test_the_connected_share_of_a_district_matches_the_dashboard(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """«Сделано, когда» of T-69: the district row and ``GET /api/dashboard/summary`` agree.

    Both endpoints are asked for the same district and their answers are compared, so a second
    definition of «подключённая школа» would fail the test instead of only the demo.
    """
    school_a, _ = await two_districts(session)
    oblast = bearer(await create_user(session, "oblast"))

    rollout = await get(api_client, SUMMARY, oblast)
    dashboard = await get(
        api_client,
        DASHBOARD,
        oblast,
        region_id=school_a.region_id,
        period_to=WORKDAY.isoformat(),
    )

    row = next(row for row in rollout["regions"] if row["region_id"] == school_a.region_id)
    assert row["schools_count"] == dashboard["schools_count"]
    assert row["devices_count"] == dashboard["devices_count"]
    assert row["schools_connected_count"] == dashboard["schools_count"]
    assert row["connected_pct"] == 100.0
    assert rollout["schools_total_count"] == 2


async def test_each_list_picks_exactly_the_school_it_should(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """The four criteria of §6.4 on a fixture that holds one school of each."""
    schools = await one_of_each(session)
    oblast = bearer(await create_user(session, "oblast"))

    summary = await get(api_client, SUMMARY, oblast)
    picked = {name: await get(api_client, SCHOOLS, oblast, filter=name) for name in schools}

    assert summary["lists"] == {
        "not_connected": 1,
        "silent": 1,
        "code_unused": 1,
        "old_version": 1,
    }
    assert summary["target_version"] == CURRENT
    assert (summary["schools_count"], summary["schools_connected_count"]) == (4, 3)
    for name, school in schools.items():
        page = picked[name]
        assert page["total"] == 1, name
        assert [item["school_id"] for item in page["items"]] == [school.id], name
    assert picked["silent"]["items"][0]["silent_days"] == SILENCE.days
    assert picked["code_unused"]["items"][0]["code_age_days"] == SILENCE.days
    assert picked["old_version"]["items"][0]["agent_versions"] == [BEHIND]
    assert picked["not_connected"]["items"][0]["devices_count"] == 0


async def test_the_silent_window_comes_from_the_settings(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """The window is a setting, not a constant of the code (ТЗ п. 11, п. 20; ADR-004).

    Silence of nine days is «молчит» by the default seven and stops being it as soon as an
    administrator gives the schools two weeks.
    """
    await one_of_each(session)
    oblast = bearer(await create_user(session, "oblast"))
    settings = await session.get(SystemSettings, 1)
    assert settings is not None

    before = await get(api_client, SCHOOLS, oblast, filter="silent")
    settings.rollout_silent_days = 14
    await session.commit()
    after = await get(api_client, SCHOOLS, oblast, filter="silent")
    summary = await get(api_client, SUMMARY, oblast)

    assert (before["total"], before["silent_days"]) == (1, 7)
    assert (after["total"], after["silent_days"]) == (0, 14)
    assert summary["lists"]["silent"] == 0


async def test_assigning_an_update_moves_the_devices_to_the_channel_of_the_version(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """«Назначить обновление»: the target version is delivered by the channel of T-50.

    A version that is not the newest of its channel cannot be delivered at all, so it is a 409
    instead of a change that never reaches an agent.
    """
    await one_of_each(session)
    await a_release(session, "0.4.0", released_ago=timedelta(days=5))
    await a_release(session, "0.5.0", channel="pilot", released_ago=timedelta(days=1))
    admin = bearer(await create_user(session, "admin"))

    assigned = await api_client.post(ASSIGN, headers=admin, json={"version": "0.5.0"})
    outdated = await api_client.post(ASSIGN, headers=admin, json={"version": CURRENT})
    unknown = await api_client.post(ASSIGN, headers=admin, json={"version": "9.9.9"})

    assert assigned.status_code == 200, assigned.text
    body = assigned.json()
    assert (body["version"], body["channel"]) == ("0.5.0", "pilot")
    # Every computer of the fixture waited on the stable channel, so all three moved.
    assert (body["devices_count"], body["devices_changed_count"]) == (3, 3)
    assert outdated.status_code == 409, outdated.text
    assert outdated.json()["type"] == "release_not_latest"
    assert unknown.status_code == 404


async def test_a_district_cannot_assign_an_update(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Changing a computer stays with ``devices:manage`` (T-36, ADR-008)."""
    school_a, _ = await two_districts(session)
    await a_release(session)
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    refused = await api_client.post(ASSIGN, headers=district, json={"version": CURRENT})

    assert refused.status_code == 403, refused.text
    assert refused.json()["type"] == "forbidden"
