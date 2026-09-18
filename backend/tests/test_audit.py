"""T-20: the audit middleware — changing actions and rejected agent requests (ТЗ п. 12, п. 16)."""

from collections.abc import AsyncIterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import Depends, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.errors import ApiError
from app.main import create_app
from app.models import AuditLog
from tests.factories import bearer, create_school, create_user, primary_point, register_device


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Application with changing panel routes of the test: the endpoints of the tasks that
    change data (T-34…T-50) are still stubs."""
    application = create_app()

    @application.patch(
        "/api/test/schools/{school_id}", dependencies=[Depends(require("schools:write"))]
    )
    async def update_test_school(school_id: int) -> dict[str, int]:
        return {"id": school_id}

    @application.post(
        "/api/test/schools/{school_id}/lines",
        status_code=201,
        dependencies=[Depends(require("schools:write"))],
    )
    async def create_test_line(school_id: int) -> dict[str, int]:
        return {"id": 77}

    @application.post(
        "/api/test/admin/users/{user_id}", dependencies=[Depends(require("users:manage"))]
    )
    async def block_test_user(user_id: int, request: Request) -> None:
        describe_action(request, action="block", changes={"is_active": {"old": True, "new": False}})

    @application.post(
        "/api/test/schools/{school_id}/fail", dependencies=[Depends(require("schools:write"))]
    )
    async def fail_test_school(school_id: int) -> None:
        raise ApiError(409, "conflict", "Не получилось")

    application.dependency_overrides[get_session] = lambda: session
    application.state.audit_sessions = lambda: nullcontext(session)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def records(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.scalars(select(AuditLog).order_by(AuditLog.id))).all()
    return [
        {
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "user_id": row.user_id,
            "user_email": row.user_email,
            "changes": row.changes,
            "error_type": row.error_type,
        }
        for row in rows
    ]


async def test_changing_panel_requests_are_logged_with_who_and_what(
    session: AsyncSession, client: AsyncClient
) -> None:
    admin = await create_user(session, "admin")
    school = await create_user(session, "school", email="school@example.kz")

    updated = await client.patch("/api/test/schools/5", headers=bearer(admin))
    created = await client.post("/api/test/schools/5/lines", headers=bearer(admin))
    blocked = await client.post(f"/api/test/admin/users/{school.id}", headers=bearer(admin))
    # Refused and failed requests change nothing and leave no record.
    forbidden = await client.patch("/api/test/schools/5", headers=bearer(school))
    failed = await client.post("/api/test/schools/5/fail", headers=bearer(admin))
    read = await client.get("/api/schools", headers=bearer(admin))

    assert [r.status_code for r in (updated, created, blocked, forbidden, failed, read)] == [
        200,
        201,
        200,
        403,
        409,
        501,
    ]
    who = {"user_id": admin.id, "user_email": "admin@example.kz", "error_type": None}
    assert await records(session) == [
        {"action": "update", "entity_type": "school", "entity_id": 5, "changes": None} | who,
        {"action": "create", "entity_type": "line", "entity_id": 77, "changes": None} | who,
        {
            "action": "block",
            "entity_type": "user",
            "entity_id": school.id,
            "changes": {"is_active": {"old": True, "new": False}},
        }
        | who,
    ]


async def test_rejected_agent_requests_are_transfer_errors(
    session: AsyncSession, client: AsyncClient
) -> None:
    school = await create_school(session)
    device, token = await register_device(session, await primary_point(session, school))
    started_at = datetime(2026, 9, 18, 5, 0, tzinfo=UTC)
    outage = {
        "started_at": started_at.isoformat(),
        "ended_at": (started_at + timedelta(minutes=5)).isoformat(),
    }
    as_device = {"Authorization": f"Device {token}"}
    beat = {"sent_at": datetime.now(UTC).isoformat(), "agent_version": "0.1.0"}

    await client.post("/api/devices/heartbeat", json=beat, headers={"Authorization": "Device 1.x"})
    await client.post("/api/outages", json={"started_at": "вчера"}, headers=as_device)
    # A duplicate is an answer, not an error (ADR-006); a success is not logged either.
    assert (await client.post("/api/outages", json=outage, headers=as_device)).status_code == 201
    assert (await client.post("/api/outages", json=outage, headers=as_device)).status_code == 409
    device.status = "blocked"
    await session.flush()
    await client.post("/api/devices/heartbeat", json=beat, headers=as_device)

    rows = await records(session)
    assert [(r["action"], r["entity_id"], r["error_type"]) for r in rows] == [
        ("transfer_error", None, "unauthorized"),
        ("transfer_error", device.id, "validation_error"),
        ("transfer_error", device.id, "device_blocked"),
    ]
    assert {r["entity_type"] for r in rows} == {"device"}


async def test_audit_log_cannot_be_changed_or_deleted(
    session: AsyncSession, client: AsyncClient
) -> None:
    admin = await create_user(session, "admin")
    await client.patch("/api/test/schools/5", headers=bearer(admin))

    for statement in ("UPDATE audit_log SET action = 'create'", "DELETE FROM audit_log"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with session.begin_nested():
                await session.execute(text(statement))
    assert len(await records(session)) == 1
