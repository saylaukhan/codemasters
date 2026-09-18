"""T-33: background exports — the request or Celery by size, the worker, the list, the purge.

The school of ``test_exports``: three measurements on 14.09 local time. The threshold of rows
is lowered in the settings instead of writing 10 001 measurements; ``in_background`` is checked
on the numbers of «Решения по умолчанию» themselves.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from kombu.exceptions import OperationalError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import SCOPE_KEY
from app.models import Export
from app.services.exports import build_pending_export, in_background, purge_expired_exports
from app.workers.celery_app import celery_app
from app.workers.tasks.exports import BUILD_EXPORT, PURGE_EXPIRED_EXPORTS
from tests.factories import bearer, create_settings, create_user
from tests.test_exports import download, measured_school, request_body, xlsx_rows


def test_more_than_10_000_rows_or_a_pdf_go_to_celery() -> None:
    assert not in_background("xlsx", 10_000, 10_000)
    assert in_background("xlsx", 10_001, 10_000)
    assert in_background("csv", 10_001, 10_000)
    assert in_background("pdf", 0, 10_000)


async def post_export(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Any:
    created = await client.post("/api/exports", json=request_body(**changes), headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


async def test_the_size_of_the_export_chooses_the_request_or_celery(
    session: AsyncSession, api_client: AsyncClient, export_queue: list[int]
) -> None:
    settings = await create_settings(session)
    await measured_school(session, "VKO-BG-001")
    headers = bearer(await create_user(session, "oblast"))

    settings.export_sync_max_rows = 3
    at_threshold = await post_export(api_client, headers)
    settings.export_sync_max_rows = 2
    above = await post_export(api_client, headers)
    waiting = await api_client.get(f"/api/exports/{above['id']}", headers=headers)
    listed = (await api_client.get("/api/exports", headers=headers)).json()

    assert at_threshold["status"] == "ready"
    assert at_threshold["rows_count"] == 3
    assert above["status"] == "pending"
    assert above["rows_count"] is None
    assert above["file_name"] is None
    assert export_queue == [above["id"]]
    assert waiting.status_code == 202
    assert waiting.json()["status"] == "pending"
    assert [(item["id"], item["status"]) for item in listed["items"]] == [
        (above["id"], "pending"),
        (at_threshold["id"], "ready"),
    ]
    assert listed["total"] == 2

    assert await build_pending_export(session, above["id"], now=datetime.now(UTC)) == "ready"
    built = (await api_client.get("/api/exports", headers=headers)).json()["items"][0]
    rows = xlsx_rows((await download(api_client, headers, above["id"])).content)

    assert built["status"] == "ready"
    assert built["rows_count"] == 3
    assert built["file_name"] == "measurements_2026-09-14_2026-09-14.xlsx"
    assert built["period_from"] == "2026-09-13T19:00:00Z"
    assert len(rows) == 4


async def test_the_worker_builds_the_file_under_the_scope_of_its_owner(
    session: AsyncSession, api_client: AsyncClient, export_queue: list[int]
) -> None:
    settings = await create_settings(session)
    settings.export_sync_max_rows = 1
    own, _ = await measured_school(session, "VKO-BG-001")
    other, _ = await measured_school(session, "VKO-BG-002")
    school_user = await create_user(session, "school", school_id=own.id)
    headers = bearer(school_user)
    blocked = await create_user(session, "oblast")

    everything = await post_export(api_client, headers, format="json")
    of_blocked = await post_export(api_client, bearer(blocked))
    blocked.is_active = False
    await session.flush()
    now = datetime.now(UTC)

    assert await build_pending_export(session, everything["id"], now=now) == "ready"
    assert await build_pending_export(session, of_blocked["id"], now=now) == "failed"
    rows = (await download(api_client, headers, everything["id"])).json()
    failed = await session.get_one(Export, of_blocked["id"])

    assert {row["school_name"] for row in rows} == {own.full_name}
    assert other.full_name not in {row["school_name"] for row in rows}
    assert len(rows) == 3
    assert failed.error == "Учётная запись заблокирована"
    assert failed.expires_at is not None
    # The worker leaves the session to the owner of the tables.
    assert SCOPE_KEY not in session.info


async def test_a_school_that_left_the_scope_fails_the_export(
    session: AsyncSession, api_client: AsyncClient, export_queue: list[int]
) -> None:
    await create_settings(session)
    own, _ = await measured_school(session, "VKO-BG-001")
    other, _ = await measured_school(session, "VKO-BG-002")
    user = await create_user(session, "school", school_id=own.id)
    headers = bearer(user)

    job = await post_export(
        api_client, headers, mode="school_report", format="pdf", school_ids=[own.id]
    )
    pending = await session.get_one(Export, job["id"])
    pending.params = pending.params | {"school_ids": [other.id]}
    await session.flush()

    assert await build_pending_export(session, job["id"], now=datetime.now(UTC)) == "failed"
    failed = await api_client.get(f"/api/exports/{job['id']}", headers=headers)
    listed = (await api_client.get("/api/exports", headers=headers)).json()["items"]

    assert failed.status_code == 409
    assert listed[0]["status"] == "failed"
    assert "вне области видимости" in listed[0]["error"]


async def test_an_unavailable_queue_fails_the_export_at_once(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await create_settings(session)
    school, _ = await measured_school(session, "VKO-BG-001")
    headers = bearer(await create_user(session, "oblast"))

    def broker_down(export_id: int) -> None:
        raise OperationalError("Error 111 connecting to localhost:6379")

    monkeypatch.setattr("app.api.exports.enqueue_build", broker_down)
    job = await post_export(
        api_client, headers, mode="school_report", format="pdf", school_ids=[school.id]
    )

    assert job["status"] == "failed"
    assert job["error"] == "Очередь фоновых выгрузок недоступна, попробуйте позже"


async def test_the_list_shows_only_the_users_own_exports_that_have_not_expired(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    await measured_school(session, "VKO-BG-001")
    owner = bearer(await create_user(session, "oblast"))
    stranger = bearer(await create_user(session, "admin"))

    kept = await post_export(api_client, owner)
    expired = await post_export(api_client, owner)
    await session.execute(
        update(Export)
        .where(Export.id == expired["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    own_list = (await api_client.get("/api/exports", headers=owner)).json()
    foreign_list = (await api_client.get("/api/exports", headers=stranger)).json()

    assert [item["id"] for item in own_list["items"]] == [kept["id"]]
    assert foreign_list == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_beat_removes_expired_files_and_stale_pending_exports(
    session: AsyncSession,
) -> None:
    settings = await create_settings(session)
    user = await create_user(session, "oblast")
    now = datetime.now(UTC)
    params = request_body()

    def export(status: str, **values: Any) -> Export:
        return Export(
            user_id=user.id, mode="raw", format="xlsx", status=status, params=params, **values
        )

    fresh = export("ready", expires_at=now + timedelta(days=1), content=b"file")
    expired = export("ready", expires_at=now - timedelta(seconds=1), content=b"file")
    failed = export("failed", expires_at=now - timedelta(seconds=1), error="нет")
    building = export("pending")
    stale = export(
        "pending", created_at=now - timedelta(days=settings.export_retention_days, seconds=1)
    )
    session.add_all([fresh, expired, failed, building, stale])
    await session.flush()

    assert await purge_expired_exports(session, now=now) == 3
    left = set(await session.scalars(select(Export.id).where(Export.user_id == user.id)))
    assert left == {fresh.id, building.id}

    schedule = {
        entry["task"]: entry["schedule"] for entry in celery_app.conf.beat_schedule.values()
    }
    assert schedule[PURGE_EXPIRED_EXPORTS] <= 60 * 60
    assert {BUILD_EXPORT, PURGE_EXPIRED_EXPORTS} <= set(celery_app.tasks)
