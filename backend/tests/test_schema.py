"""Schema v1 (T-02) on a migrated database: school → line → point → device → measurement."""

import uuid
from datetime import UTC, datetime
from ipaddress import ip_address, ip_network

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConnectionType,
    Device,
    Line,
    Measurement,
    MonitoringPoint,
    Provider,
    Region,
    School,
)


async def create_chain(session: AsyncSession) -> tuple[School, Measurement]:
    """Insert region, provider, school, line, point, device and one measurement of that device."""
    region = Region(code="UK", name="Усть-Каменогорск")
    provider = Provider(name="Тестовый провайдер")
    connection_type = ConnectionType(code="fiber", name="Оптоволокно")
    session.add_all([region, provider, connection_type])
    await session.flush()

    school = School(
        school_code="VKO-UK-001",
        full_name="Школа-гимназия № 1",
        region_id=region.id,
        geom=WKTElement("POINT(82.6153 49.9483)", srid=4326),
    )
    session.add(school)
    await session.flush()

    line = Line(
        school_id=school.id,
        provider_id=provider.id,
        connection_type_id=connection_type.id,
        status="main",
        contract_down_mbps=100,
        contract_up_mbps=100,
        ip_ranges=[ip_network("192.0.2.0/24")],
    )
    session.add(line)
    await session.flush()

    point = MonitoringPoint(school_id=school.id, line_id=line.id, name="Серверная", is_primary=True)
    session.add(point)
    await session.flush()

    device = Device(
        device_uid=str(uuid.uuid4()), monitoring_point_id=point.id, token_hash="test-token-hash"
    )
    session.add(device)
    await session.flush()

    measurement = Measurement(
        measurement_uuid=uuid.uuid4(),
        measured_at=datetime(2026, 9, 16, 6, 42, tzinfo=UTC),
        device_id=device.id,
        line_id=line.id,
        download_mbps=94.5,
        upload_mbps=88.1,
        ping_ms=12.0,
        jitter_ms=1.5,
        packet_loss_pct=0.0,
        connection_status="online",
        external_ip=ip_address("192.0.2.15"),
        iface_type="ethernet",
    )
    session.add(measurement)
    await session.flush()
    return school, measurement


async def test_measurement_is_linked_to_school_through_device(session: AsyncSession) -> None:
    school, measurement = await create_chain(session)

    # School ID is derived from the device binding only (ADR-005).
    school_id = await session.scalar(
        select(School.id)
        .join(Line, Line.school_id == School.id)
        .join(MonitoringPoint, MonitoringPoint.line_id == Line.id)
        .join(Device, Device.monitoring_point_id == MonitoringPoint.id)
        .join(Measurement, Measurement.device_id == Device.id)
        .where(Measurement.measurement_uuid == measurement.measurement_uuid)
    )
    assert school_id == school.id

    stored = await session.get_one(Measurement, (measurement.id, measurement.measured_at))
    await session.refresh(stored)
    assert stored.received_at.tzinfo is not None
    assert stored.external_ip == ip_address("192.0.2.15")
    line = await session.get_one(Line, measurement.line_id)
    await session.refresh(line)
    assert line.ip_ranges == [ip_network("192.0.2.0/24")]
    assert await session.scalar(select(func.ST_AsText(School.geom))) == "POINT(82.6153 49.9483)"


async def test_time_series_tables_are_hypertables(session: AsyncSession) -> None:
    hypertables = await session.scalars(
        text("SELECT hypertable_name FROM timescaledb_information.hypertables")
    )

    assert set(hypertables) == {"measurements", "heartbeats"}


async def test_repeated_measurement_uuid_is_rejected(session: AsyncSession) -> None:
    _, measurement = await create_chain(session)

    session.add(
        Measurement(
            measurement_uuid=measurement.measurement_uuid,
            measured_at=measurement.measured_at,
            device_id=measurement.device_id,
            line_id=measurement.line_id,
            connection_status="offline",
        )
    )

    with pytest.raises(IntegrityError, match="uq_measurements_measurement_uuid"):
        await session.flush()


async def test_point_cannot_use_line_of_another_school(session: AsyncSession) -> None:
    school, measurement = await create_chain(session)
    other_school = School(
        school_code="VKO-UK-002", full_name="Школа № 2", region_id=school.region_id
    )
    session.add(other_school)
    await session.flush()

    session.add(
        MonitoringPoint(school_id=other_school.id, line_id=measurement.line_id, name="Кабинет 12")
    )

    with pytest.raises(IntegrityError, match="fk_monitoring_points_line_id_school_id_lines"):
        await session.flush()


async def test_every_foreign_key_has_an_index(session: AsyncSession) -> None:
    # A foreign key is covered when some index starts with exactly its columns, in order.
    uncovered = await session.scalars(
        text(
            """
            SELECT c.conname
            FROM pg_constraint AS c
            WHERE c.contype = 'f'
              AND c.connamespace = 'public'::regnamespace
              AND NOT EXISTS (
                  SELECT 1
                  FROM pg_index AS i
                  WHERE i.indrelid = c.conrelid
                    AND (string_to_array(i.indkey::text, ' ')::int2[])[1:cardinality(c.conkey)]
                        = c.conkey
              )
            ORDER BY c.conname
            """
        )
    )

    assert list(uncovered) == []
