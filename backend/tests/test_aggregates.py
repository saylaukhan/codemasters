"""T-19: continuous aggregates m_hourly and m_daily (ТЗ п. 5, plan.md §5, ADR-014).

The question this task closes is where a day begins: a measurement at 02:00 Asia/Almaty belongs
to that school day, not to the previous UTC one. Every number of the views is compared here
with the same number counted from the raw measurements, so a mistake in the bucket, in the
Wi-Fi filter or in the count of problems shows up as a difference, not as an opinion.
"""

from datetime import UTC, datetime, timedelta
from statistics import fmean
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, MDaily, Measurement, MHourly, School
from tests.factories import create_school, primary_point, register_device

ALMATY = ZoneInfo("Asia/Almaty")

# Measurements of one device, in local time of the school. The night one is the point of the
# task: 02:00 in Almaty is 21:00 of the previous day in UTC and still belongs to the 18th.
SAMPLES = [
    # local moment, download, upload, ping, jitter, loss, status, interface
    ((2026, 9, 17, 23, 0), 70.0, 60.0, 20.0, 2.0, 0.0, "normal", "ethernet"),
    ((2026, 9, 18, 2, 0), 90.0, 80.0, 18.0, 1.0, 0.0, "normal", "ethernet"),
    ((2026, 9, 18, 14, 0), 50.0, 40.0, 60.0, 12.0, 1.0, "unstable", "ethernet"),
    ((2026, 9, 18, 14, 20), 10.0, 8.0, 140.0, 25.0, 7.0, "critical", "ethernet"),
    # No connection: it counts as a measurement and as a problem, but averages nothing.
    ((2026, 9, 18, 16, 0), None, None, None, None, None, "offline", "ethernet"),
    # Wi-Fi measures the air, not the line, and is in neither view (ADR-012).
    ((2026, 9, 18, 15, 0), 5.0, 4.0, 300.0, 40.0, 9.0, "critical", "wifi"),
]

DAY = datetime(2026, 9, 18, tzinfo=ALMATY)
PREVIOUS_DAY = datetime(2026, 9, 17, tzinfo=ALMATY)
PROBLEM_STATUSES = {"unstable", "critical", "offline"}


def moment(sample: tuple[Any, ...]) -> datetime:
    """The moment of a sample as the agent measured it, in the local time of the school."""
    return datetime(*sample[0], tzinfo=ALMATY)


def wired(samples: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """Samples that rate the line: everything but Wi-Fi (ADR-012)."""
    return [sample for sample in samples if sample[7] != "wifi"]


def within(samples: list[tuple[Any, ...]], start: datetime, hours: int) -> list[tuple[Any, ...]]:
    """Samples of the bucket that starts at ``start`` and lasts ``hours``."""
    end = start + timedelta(hours=hours)
    return [sample for sample in wired(samples) if start <= moment(sample) < end]


async def measuring_device(session: AsyncSession) -> tuple[School, Line, Device]:
    """A school with one device on its main line and every sample already measured by it."""
    school = await create_school(session)
    point = await primary_point(session, school)
    device, _ = await register_device(session, point)
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()

    for sample in SAMPLES:
        _, download, upload, ping, jitter, loss, quality, iface = sample
        session.add(
            Measurement(
                measurement_uuid=uuid4(),
                measured_at=moment(sample).astimezone(UTC),
                device_id=device.id,
                line_id=line.id,
                download_mbps=download,
                upload_mbps=upload,
                ping_ms=ping,
                jitter_ms=jitter,
                packet_loss_pct=loss,
                connection_status="offline" if quality == "offline" else "online",
                iface_type=iface,
                quality_status=quality,
            )
        )
    await session.flush()
    return school, line, device


def assert_matches_the_raw_measurements(
    row: MDaily | MHourly, samples: list[tuple[Any, ...]]
) -> None:
    """Compare one row of a view with the same numbers counted from the measurements."""
    downloads = [sample[1] for sample in samples if sample[1] is not None]
    pings = [sample[3] for sample in samples if sample[3] is not None]

    assert row.measurements_count == len(samples)
    assert row.problem_count == len([sample for sample in samples if sample[6] in PROBLEM_STATUSES])
    assert row.avg_download_mbps == pytest.approx(fmean(downloads))
    assert row.min_download_mbps == min(downloads)
    assert row.max_download_mbps == max(downloads)
    assert row.avg_ping_ms == pytest.approx(fmean(pings))
    assert row.max_ping_ms == max(pings)


async def test_a_day_of_m_daily_is_a_day_of_almaty(session: AsyncSession) -> None:
    """02:00 in Almaty is 21:00 UTC of the day before and still belongs to the school day."""
    _, line, device = await measuring_device(session)

    rows = (await session.scalars(select(MDaily).order_by(MDaily.bucket))).all()

    assert [row.bucket for row in rows] == [PREVIOUS_DAY, DAY]
    day = rows[1]
    assert (day.line_id, day.device_id) == (line.id, device.id)
    # Four of the day: the night one at 02:00, two of the afternoon and the one without
    # connection. The Wi-Fi measurement of 15:00 is in none of them.
    assert_matches_the_raw_measurements(day, within(SAMPLES, DAY, hours=24))
    assert day.measurements_count == 4
    assert day.avg_download_mbps == 50.0


async def test_m_hourly_splits_the_day_into_the_hours_of_almaty(session: AsyncSession) -> None:
    await measuring_device(session)

    rows = (await session.scalars(select(MHourly).order_by(MHourly.bucket))).all()

    assert [row.bucket for row in rows] == [
        datetime(2026, 9, 17, 23, tzinfo=ALMATY),
        datetime(2026, 9, 18, 2, tzinfo=ALMATY),
        # Two measurements of 14:00 and 14:20 share one hour; 15:00 is Wi-Fi and is dropped.
        datetime(2026, 9, 18, 14, tzinfo=ALMATY),
        datetime(2026, 9, 18, 16, tzinfo=ALMATY),
    ]
    afternoon = rows[2]
    assert_matches_the_raw_measurements(
        afternoon, within(SAMPLES, datetime(2026, 9, 18, 14, tzinfo=ALMATY), hours=1)
    )
    # The hour of the measurement without connection counts it and averages nothing.
    assert (rows[3].measurements_count, rows[3].problem_count) == (1, 1)
    assert rows[3].avg_download_mbps is None


async def test_wifi_measurements_are_in_neither_view(session: AsyncSession) -> None:
    await measuring_device(session)

    hours = (await session.scalars(select(MHourly.bucket))).all()
    days = (await session.scalars(select(MDaily.measurements_count))).all()

    assert datetime(2026, 9, 18, 15, tzinfo=ALMATY) not in hours
    # Five measurements were stored for the two days; the Wi-Fi one is not counted.
    assert sum(days) == len(wired(SAMPLES))


async def test_both_views_are_continuous_aggregates_with_a_refresh_policy(
    session: AsyncSession,
) -> None:
    """Analytics reads a view that keeps itself up to date, not a query over raw measurements."""
    views = (
        await session.execute(
            text(
                "SELECT view_name, materialized_only "
                "FROM timescaledb_information.continuous_aggregates"
            )
        )
    ).all()
    jobs = (
        await session.scalars(
            text(
                "SELECT hypertable_name FROM timescaledb_information.jobs "
                "WHERE proc_name = 'policy_refresh_continuous_aggregate'"
            )
        )
    ).all()

    # Real-time aggregation: the current hour is answered before the policy materializes it.
    assert sorted(views) == [("m_daily", False), ("m_hourly", False)]
    assert sorted(jobs) == ["m_daily", "m_hourly"]
