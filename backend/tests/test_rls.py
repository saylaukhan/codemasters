"""T-20: row-level security by ``app.user_scope`` — a stranger does not see (ТЗ п. 16, ADR-008).

Two districts, A and B. School A has a main line of provider A and a reserve line of provider
B; school B has one line of provider B. Each line has a point, a computer, a measurement and a
heartbeat. Every role must see exactly its part of this, first through the policies directly,
then through a panel request guarded by ``require``.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.rls import apply_scope, clear_scope
from app.core.db import get_session
from app.main import create_app
from app.models import (
    Device,
    Heartbeat,
    Line,
    Measurement,
    MonitoringPoint,
    School,
    SchoolContact,
)
from tests.factories import bearer, create_school, create_user, primary_point, register_device


@dataclass
class Oblast:
    """Ids of the two districts, their providers and the named lines."""

    region_a: int
    region_b: int
    school_a: int
    provider_a: int
    provider_b: int
    lines: dict[int, str]


async def build_oblast(session: AsyncSession) -> Oblast:
    school_a = await create_school(session, school_code="VKO-A-001")
    school_b = await create_school(session, school_code="VKO-B-001")
    main_a = (await session.scalars(select(Line).where(Line.school_id == school_a.id))).one()
    main_b = (await session.scalars(select(Line).where(Line.school_id == school_b.id))).one()
    reserve_a = Line(school_id=school_a.id, provider_id=main_b.provider_id, status="reserve")
    session.add(reserve_a)
    await session.flush()
    reserve_point = MonitoringPoint(school_id=school_a.id, line_id=reserve_a.id, name="Резерв")
    session.add(reserve_point)
    session.add_all(
        [
            SchoolContact(school_id=school_a.id, full_name="Директор A"),
            SchoolContact(school_id=school_b.id, full_name="Директор B"),
        ]
    )
    await session.flush()

    points = {
        "PC-A": (await primary_point(session, school_a), main_a.id),
        "PC-AR": (reserve_point, reserve_a.id),
        "PC-B": (await primary_point(session, school_b), main_b.id),
    }
    now = datetime.now(UTC)
    for uid, (point, line_id) in points.items():
        device, _ = await register_device(session, point, device_uid=uid)
        session.add(Heartbeat(device_id=device.id, ts=now, online=True))
        session.add(
            Measurement(
                measured_at=now,
                measurement_uuid=uuid.uuid4(),
                device_id=device.id,
                line_id=line_id,
                connection_status="online",
            )
        )
    await session.flush()
    return Oblast(
        region_a=school_a.region_id,
        region_b=school_b.region_id,
        school_a=school_a.id,
        provider_a=main_a.provider_id,
        provider_b=main_b.provider_id,
        lines={main_a.id: "A-main", reserve_a.id: "A-reserve", main_b.id: "B-main"},
    )


async def visible(session: AsyncSession, oblast: Oblast, scope: str) -> dict[str, set[str]]:
    """What the panel role sees in every table with a scope, under ``scope``."""
    await apply_scope(session, scope)
    try:
        return {
            "schools": set(await session.scalars(select(School.school_code))),
            "contacts": set(await session.scalars(select(SchoolContact.full_name))),
            "lines": {oblast.lines[i] for i in await session.scalars(select(Line.id))},
            "points": {
                oblast.lines[i] for i in await session.scalars(select(MonitoringPoint.line_id))
            },
            "devices": set(await session.scalars(select(Device.device_uid))),
            "measurements": {
                oblast.lines[i] for i in await session.scalars(select(Measurement.line_id))
            },
            "heartbeats": {str(i) for i in await session.scalars(select(Heartbeat.device_id))},
        }
    finally:
        await clear_scope(session)


async def device_ids(session: AsyncSession, *uids: str) -> set[str]:
    return {
        str(i) for i in await session.scalars(select(Device.id).where(Device.device_uid.in_(uids)))
    }


async def test_each_scope_sees_only_its_schools_lines_and_devices(session: AsyncSession) -> None:
    oblast = await build_oblast(session)
    a = await device_ids(session, "PC-A")
    ar = await device_ids(session, "PC-AR")
    b = await device_ids(session, "PC-B")

    school_a = {
        "schools": {"VKO-A-001"},
        "contacts": {"Директор A"},
        "lines": {"A-main", "A-reserve"},
        "points": {"A-main", "A-reserve"},
        "devices": {"PC-A", "PC-AR"},
        "measurements": {"A-main", "A-reserve"},
        "heartbeats": a | ar,
    }
    everything = {
        "schools": {"VKO-A-001", "VKO-B-001"},
        "contacts": {"Директор A", "Директор B"},
        "lines": {"A-main", "A-reserve", "B-main"},
        "points": {"A-main", "A-reserve", "B-main"},
        "devices": {"PC-A", "PC-AR", "PC-B"},
        "measurements": {"A-main", "A-reserve", "B-main"},
        "heartbeats": a | ar | b,
    }
    # Provider B serves both schools, but at school A only through the reserve line.
    provider_b = {
        "schools": {"VKO-A-001", "VKO-B-001"},
        "contacts": {"Директор A", "Директор B"},
        "lines": {"A-reserve", "B-main"},
        "points": {"A-reserve", "B-main"},
        "devices": {"PC-AR", "PC-B"},
        "measurements": {"A-reserve", "B-main"},
        "heartbeats": ar | b,
    }
    nothing: dict[str, set[str]] = {key: set() for key in everything}

    assert await visible(session, oblast, f"school:{oblast.school_a}") == school_a
    assert await visible(session, oblast, f"region:{oblast.region_a}") == school_a
    assert (await visible(session, oblast, f"region:{oblast.region_b}"))["lines"] == {"B-main"}
    assert await visible(session, oblast, f"provider:{oblast.provider_b}") == provider_b
    assert (await visible(session, oblast, f"provider:{oblast.provider_a}"))["lines"] == {"A-main"}
    assert await visible(session, oblast, "all") == everything
    assert await visible(session, oblast, "") == nothing
    # After the scope the session is the owner again and sees everything.
    assert set(await session.scalars(select(School.school_code))) == everything["schools"]


async def test_panel_cannot_write_outside_its_scope_nor_delete(session: AsyncSession) -> None:
    oblast = await build_oblast(session)

    await apply_scope(session, f"region:{oblast.region_a}")
    try:
        with pytest.raises(DBAPIError, match="row-level security"):
            async with session.begin_nested():
                session.add(
                    School(school_code="VKO-B-002", full_name="Чужая", region_id=oblast.region_b)
                )
                await session.flush()
        with pytest.raises(DBAPIError, match="permission denied"):
            async with session.begin_nested():
                await session.execute(delete(SchoolContact))
    finally:
        await clear_scope(session)


@pytest.fixture
async def scoped_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Application with a panel route that lists the schools its session can see."""
    application = create_app()

    @application.get("/api/test/visible-schools", dependencies=[Depends(require("schools:read"))])
    async def visible_schools(db: Annotated[AsyncSession, Depends(get_session)]) -> list[str]:
        return list(await db.scalars(select(School.school_code).order_by(School.school_code)))

    application.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("school", ["VKO-A-001"]),
        ("district", ["VKO-A-001"]),
        ("provider", ["VKO-A-001", "VKO-B-001"]),
        ("oblast", ["VKO-A-001", "VKO-B-001"]),
        ("admin", ["VKO-A-001", "VKO-B-001"]),
    ],
)
async def test_a_request_of_each_role_sees_only_its_schools(
    session: AsyncSession, scoped_client: AsyncClient, role: str, expected: list[str]
) -> None:
    oblast = await build_oblast(session)
    scope = {
        "school": {"school_id": oblast.school_a},
        "district": {"region_id": oblast.region_a},
        "provider": {"provider_id": oblast.provider_b},
    }.get(role, {})
    user = await create_user(session, role, **scope)

    response = await scoped_client.get("/api/test/visible-schools", headers=bearer(user))

    assert response.status_code == 200, response.text
    assert response.json() == expected
    # The request left the session to the owner: the test can write outside the scope again.
    await create_school(session, school_code="VKO-B-003")
    assert await session.scalar(text("SELECT current_setting('app.user_scope', true)")) in (
        "",
        None,
    )
