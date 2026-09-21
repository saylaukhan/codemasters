"""T-37: threshold profiles, schedules, working hours and system settings in the admin panel.

Nothing of it is in the code of the agent or the panel (ТЗ п. 11, п. 20; ADR-004): Область and
Администратор change it, and the agent gets the new values with a new ETag of its configuration.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Line, ThresholdProfile
from app.services.status import school_status
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

ALMATY = ZoneInfo("Asia/Almaty")
# Tuesday 12:00 Asia/Almaty: inside the default working hours 08:00–18:00, Mon–Sat.
TUESDAY_NOON = datetime(2026, 9, 22, 12, 0, tzinfo=ALMATY)

THRESHOLDS = {
    "download_min_mbps": 50.0,
    "upload_min_mbps": 25.0,
    "ping_max_ms": 60.0,
    "jitter_max_ms": 20.0,
    "packet_loss_max_pct": 1.0,
}
SLOTS = [
    {"start": "13:00:00", "end": "13:30:00"},
    {"start": "09:00:00", "end": "09:30:00"},
    {"start": "15:00:00", "end": "15:30:00"},
]


def ok(response: Response, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


def problem(response: Response, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    return body


async def global_profile_id(session: AsyncSession) -> int:
    profile_id = await session.scalar(
        select(ThresholdProfile.id).where(ThresholdProfile.scope == "global")
    )
    assert profile_id is not None
    return profile_id


async def test_district_user_cannot_change_thresholds_schedules_or_settings(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    await create_settings(session)
    district = bearer(await create_user(session, "district", region_id=school.region_id))

    for path in ("/api/admin/thresholds", "/api/admin/schedules", "/api/admin/settings"):
        problem(await api_client.get(path, headers=district), 403, "forbidden")
    problem(
        await api_client.patch(
            "/api/admin/settings",
            json={"speedtest": {"librespeed_url": "https://evil.example"}},
            headers=district,
        ),
        403,
        "forbidden",
    )
    problem(
        await api_client.patch(
            f"/api/schools/{school.id}",
            json={"working_hours": {"weekdays": ["mon"], "start": "09:00", "end": "10:00"}},
            headers=district,
        ),
        403,
        "forbidden",
    )


async def test_district_and_line_profiles_are_created_changed_and_listed(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    line_id = await session.scalar(select(Line.id).where(Line.school_id == school.id))
    oblast = bearer(await create_user(session, "oblast"))

    district = ok(
        await api_client.post(
            "/api/admin/thresholds",
            json={
                "scope": "district",
                "region_id": school.region_id,
                "thresholds": THRESHOLDS,
                "unstable_deviation_pct": 30,
            },
            headers=oblast,
        ),
        201,
    )
    line = ok(
        await api_client.post(
            "/api/admin/thresholds",
            json={
                "scope": "line",
                "line_id": line_id,
                "thresholds": THRESHOLDS,
                "unstable_deviation_pct": 30,
            },
            headers=oblast,
        ),
        201,
    )
    # The share of «Нестабильно» against «Критично» is changed like any other value.
    changed = ok(
        await api_client.patch(
            f"/api/admin/thresholds/{line['id']}",
            json={"unstable_deviation_pct": 15, "thresholds": THRESHOLDS | {"ping_max_ms": 80}},
            headers=oblast,
        )
    )

    assert district["region_name"] == f"Район {school.school_code}"
    assert (line["school_id"], line["line_status"]) == (school.id, "main")
    assert changed["unstable_deviation_pct"] == 15
    assert changed["thresholds"]["ping_max_ms"] == 80
    listed = ok(await api_client.get("/api/admin/thresholds", headers=oblast))
    assert [item["scope"] for item in listed["items"]] == ["global", "district", "line"]
    # A target has one profile; the global one is never switched off.
    problem(
        await api_client.post(
            "/api/admin/thresholds",
            json={
                "scope": "line",
                "line_id": line_id,
                "thresholds": THRESHOLDS,
                "unstable_deviation_pct": 30,
            },
            headers=oblast,
        ),
        409,
        "threshold_profile_exists",
    )
    problem(
        await api_client.patch(
            f"/api/admin/thresholds/{await global_profile_id(session)}",
            json={"is_active": False},
            headers=oblast,
        ),
        409,
        "global_threshold_profile_required",
    )
    problem(
        await api_client.post(
            "/api/admin/thresholds",
            json={
                "scope": "line",
                "line_id": 999_999,
                "thresholds": THRESHOLDS,
                "unstable_deviation_pct": 30,
            },
            headers=oblast,
        ),
        422,
        "validation_error",
    )
    audit = await session.scalar(
        select(AuditLog.changes).where(
            AuditLog.entity_type == "threshold_profile", AuditLog.action == "update"
        )
    )
    assert audit is not None and audit["unstable_deviation_pct"] == {"old": 30.0, "new": 15.0}


async def test_schedule_takes_three_to_five_slots_and_rejects_overlapping_ones(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    oblast = bearer(await create_user(session, "oblast"))

    def body(slots: list[dict[str, str]]) -> dict[str, Any]:
        return {"scope": "school", "school_id": school.id, "slots": slots}

    for slots in (
        SLOTS[:2],
        SLOTS + [{"start": f"1{hour}:40:00", "end": f"1{hour}:50:00"} for hour in range(3)],
        SLOTS[:2] + [{"start": "13:15:00", "end": "13:45:00"}],
    ):
        problem(
            await api_client.post("/api/admin/schedules", json=body(slots), headers=oblast),
            422,
            "validation_error",
        )
    created = ok(
        await api_client.post("/api/admin/schedules", json=body(SLOTS), headers=oblast), 201
    )

    # Slots are kept by their start.
    assert [slot["start"] for slot in created["slots"]] == ["09:00:00", "13:00:00", "15:00:00"]
    assert created["school_name"] == f"Школа {school.school_code}"
    problem(
        await api_client.patch(
            f"/api/admin/schedules/{created['id']}",
            json={"slots": SLOTS[:2] + [{"start": "09:20:00", "end": "09:50:00"}]},
            headers=oblast,
        ),
        422,
        "validation_error",
    )
    problem(
        await api_client.post("/api/admin/schedules", json=body(SLOTS), headers=oblast),
        409,
        "schedule_exists",
    )
    listed = ok(await api_client.get("/api/admin/schedules", headers=oblast))
    global_id = listed["items"][0]["id"]
    assert [item["scope"] for item in listed["items"]] == ["global", "school"]
    problem(
        await api_client.patch(
            f"/api/admin/schedules/{global_id}", json={"is_active": False}, headers=oblast
        ),
        409,
        "global_schedule_required",
    )


async def test_working_hours_are_set_per_school_and_judge_its_silence(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    other = await create_school(session, school_code="VKO-UK-002")
    await create_settings(session)
    oblast = bearer(await create_user(session, "oblast"))
    mondays = {"weekdays": ["mon"], "start": "09:00:00", "end": "13:00:00"}
    # A computer of each school that has never reported: the schools differ by their hours
    # only. A school without a computer at all says nothing about its line («Нет данных», T-44).
    for silent in (school, other):
        await register_device(
            session, await primary_point(session, silent), device_uid=silent.school_code
        )

    updated = ok(
        await api_client.patch(
            f"/api/schools/{school.id}", json={"working_hours": mondays}, headers=oblast
        )
    )

    assert updated["working_hours"] == mondays
    # Silence on a Tuesday noon: outside the hours of this school, inside the default ones.
    assert await school_status(session, school.id, now=TUESDAY_NOON) == "no_data"
    assert await school_status(session, other.id, now=TUESDAY_NOON) == "offline"
    detail = ok(await api_client.get(f"/api/schools/{other.id}", headers=oblast))
    assert detail["working_hours"]["weekdays"] == ["mon", "tue", "wed", "thu", "fri", "sat"]


async def test_settings_and_thresholds_reach_the_agent_with_a_new_etag(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    await create_settings(session)
    _, token = await register_device(session, await primary_point(session, school))
    device = {"Authorization": f"Device {token}"}
    oblast = bearer(await create_user(session, "oblast"))

    first = await api_client.get("/api/agent/config", headers=device)
    etag = first.headers["etag"]
    settings = ok(
        await api_client.patch(
            "/api/admin/settings",
            json={
                "speedtest": {
                    "librespeed_url": "https://speed2.example.kz",
                    "ndt7_url": "wss://ndt.example.kz",
                },
                "availability_min_pct": 98.5,
            },
            headers=oblast,
        )
    )
    ok(
        await api_client.patch(
            f"/api/admin/thresholds/{await global_profile_id(session)}",
            json={"thresholds": THRESHOLDS},
            headers=oblast,
        )
    )
    changed = await api_client.get("/api/agent/config", headers=device | {"If-None-Match": etag})

    assert settings["availability_min_pct"] == 98.5
    assert settings["incident_auto_close_hours"] == 24
    assert changed.status_code == 200, changed.text
    assert changed.headers["etag"] != etag
    assert changed.json()["speedtest"] == {
        "librespeed_url": "https://speed2.example.kz",
        "ndt7_url": "wss://ndt.example.kz",
    }
    assert changed.json()["thresholds"] == THRESHOLDS
    # An agent silent for less than one heartbeat interval would already be «Нет соединения».
    problem(
        await api_client.patch(
            "/api/admin/settings", json={"offline_after_s": 300}, headers=oblast
        ),
        422,
        "validation_error",
    )
    assert ok(await api_client.get("/api/admin/settings", headers=oblast))["offline_after_s"] == 900


async def test_the_queue_retention_is_changed_in_the_panel_and_reaches_the_agent(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """Срок очереди агента — настройка админки, а не константа кода (ТЗ п. 11, п. 20; ADR-006).

    Изменение попадает в журнал администратора, как и у соседних полей, и приходит агенту
    новой конфигурацией с новым ETag (T-17).
    """
    school = await create_school(session)
    await create_settings(session)
    _, token = await register_device(session, await primary_point(session, school))
    device = {"Authorization": f"Device {token}"}
    oblast = bearer(await create_user(session, "oblast"))

    first = await api_client.get("/api/agent/config", headers=device)
    etag = first.headers["etag"]
    settings = ok(
        await api_client.patch(
            "/api/admin/settings", json={"agent_queue_retention_days": 95}, headers=oblast
        )
    )
    changed = await api_client.get("/api/agent/config", headers=device | {"If-None-Match": etag})

    assert first.json()["queue_retention_days"] == 30
    assert settings["agent_queue_retention_days"] == 95
    assert changed.status_code == 200, changed.text
    assert changed.headers["etag"] != etag
    assert changed.json()["queue_retention_days"] == 95
    audit = await session.scalar(
        select(AuditLog.changes).where(
            AuditLog.entity_type == "setting", AuditLog.action == "update"
        )
    )
    assert audit is not None
    assert audit["agent_queue_retention_days"] == {"old": 30, "new": 95}
    # Год — внешняя граница: дальше это уже не досылка очереди, а переписывание истории.
    problem(
        await api_client.patch(
            "/api/admin/settings", json={"agent_queue_retention_days": 400}, headers=oblast
        ),
        422,
        "validation_error",
    )
