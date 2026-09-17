"""T-16: status of a school and its availability (ТЗ п. 11, п. 13; ADR-004, ADR-014).

Time is substituted everywhere instead of waiting for it: ``school_status`` takes the moment it
judges, and availability takes the period it counts. The measurements carry the ``quality_status``
T-18 will fill in on receipt.
"""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Heartbeat, Line, Measurement, MonitoringPoint, Outage, School
from app.services.availability import school_availability
from app.services.status import school_status
from tests.factories import create_school, create_settings, primary_point, register_device

ALMATY = ZoneInfo("Asia/Almaty")
# Friday 14:00 Asia/Almaty: inside the default working hours 08:00–18:00, Mon–Sat.
WORKDAY = datetime(2026, 9, 18, 14, 0, tzinfo=ALMATY)
# Friday 22:00 Asia/Almaty: a working day, but the school is closed and the computers are off.
NIGHT = datetime(2026, 9, 18, 22, 0, tzinfo=ALMATY)

# Series of the last measurements, newest first, and the status of the school they give.
SERIES = [
    (["normal", "normal", "normal"], "normal"),
    # A single deviation among the last three does not colour the school; two of three do.
    (["critical", "normal", "normal"], "normal"),
    (["critical", "critical", "normal"], "critical"),
    (["critical", "unstable", "normal"], "unstable"),
    (["offline", "offline", "critical"], "offline"),
    # Only the last three count, however bad the older ones were.
    (["normal", "normal", "normal", "critical", "critical"], "normal"),
    # Fewer measurements than three: the median of what there is.
    (["unstable"], "unstable"),
]


async def line_of(session: AsyncSession, school: School, status: str = "main") -> Line:
    return (
        await session.scalars(
            select(Line).where(Line.school_id == school.id, Line.status == status)
        )
    ).one()


async def add_reserve_line(session: AsyncSession, school: School) -> MonitoringPoint:
    """Reserve line of the school with a monitoring point of its own (ТЗ п. 10, ADR-003)."""
    main = await line_of(session, school)
    line = Line(school_id=school.id, provider_id=main.provider_id, status="reserve")
    session.add(line)
    await session.flush()
    point = MonitoringPoint(school_id=school.id, line_id=line.id, name="Резервная линия")
    session.add(point)
    await session.flush()
    return point


async def alive(session: AsyncSession, device: Device, moment: datetime) -> None:
    """Heartbeat of the device at ``moment``, as the endpoint records it."""
    device.last_seen_at = moment
    session.add(Heartbeat(device_id=device.id, ts=moment, online=True))
    await session.flush()


async def measured(
    session: AsyncSession,
    device: Device,
    line: Line,
    *,
    at: datetime,
    quality_status: str | None,
    iface_type: str = "ethernet",
) -> None:
    """One measurement already evaluated by the server (T-18 does the evaluating)."""
    session.add(
        Measurement(
            measurement_uuid=uuid.uuid4(),
            measured_at=at,
            device_id=device.id,
            line_id=line.id,
            connection_status="offline" if quality_status == "offline" else "online",
            iface_type=iface_type,
            quality_status=quality_status,
        )
    )
    await session.flush()


async def test_the_status_of_a_school_is_the_median_of_its_last_measurements(
    session: AsyncSession,
) -> None:
    await create_settings(session)

    for number, (series, expected) in enumerate(SERIES):
        school = await create_school(session, school_code=f"VKO-UK-{number:03d}")
        device, _ = await register_device(
            session, await primary_point(session, school), device_uid=f"PC-{number}"
        )
        await alive(session, device, WORKDAY - timedelta(minutes=1))
        line = await line_of(session, school)
        for age, quality_status in enumerate(series):
            await measured(
                session,
                device,
                line,
                at=WORKDAY - timedelta(hours=age + 1),
                quality_status=quality_status,
            )

        assert await school_status(session, school.id, now=WORKDAY) == expected, series


async def test_a_silent_agent_is_offline_in_working_hours_and_no_data_outside_them(
    session: AsyncSession,
) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    line = await line_of(session, school)
    await measured(session, device, line, at=WORKDAY - timedelta(hours=1), quality_status="normal")

    await alive(session, device, WORKDAY - timedelta(minutes=1))
    fresh = await school_status(session, school.id, now=WORKDAY)
    await alive(session, device, WORKDAY - timedelta(minutes=20))
    silent = await school_status(session, school.id, now=WORKDAY)
    await alive(session, device, NIGHT - timedelta(minutes=20))
    at_night = await school_status(session, school.id, now=NIGHT)

    # 15 minutes of silence in working hours is «Нет соединения»; outside them the computer is
    # simply switched off, and «Нет данных» is not a status of quality (ADR-004, ADR-014).
    assert (fresh, silent, at_night) == ("normal", "offline", "no_data")


async def test_wifi_and_the_reserve_line_do_not_rate_the_school(session: AsyncSession) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    await alive(session, device, WORKDAY - timedelta(minutes=1))
    main = await line_of(session, school)
    reserve_point = await add_reserve_line(session, school)
    reserve_device, _ = await register_device(session, reserve_point, device_uid="PC-RESERVE")
    reserve = await line_of(session, school, status="reserve")

    await measured(session, device, main, at=WORKDAY - timedelta(hours=3), quality_status="normal")
    for age, (line, device_of_line, iface_type) in enumerate(
        [(main, device, "wifi"), (reserve, reserve_device, "ethernet")]
    ):
        await measured(
            session,
            device_of_line,
            line,
            at=WORKDAY - timedelta(minutes=age + 1),
            quality_status="critical",
            iface_type=iface_type,
        )

    # Both newer measurements are ignored: Wi-Fi measures the air and the reserve line is not
    # what the school is judged by (ADR-004, ADR-012).
    assert await school_status(session, school.id, now=WORKDAY) == "normal"


async def test_a_school_without_measurements_has_no_data(session: AsyncSession) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    await alive(session, device, WORKDAY - timedelta(minutes=1))
    line = await line_of(session, school)
    # A measurement the server has not evaluated yet says nothing about the school (T-18).
    await measured(session, device, line, at=WORKDAY - timedelta(hours=1), quality_status=None)

    assert await school_status(session, school.id, now=WORKDAY) == "no_data"


async def heartbeats_of_the_working_day(
    session: AsyncSession, device: Device, day: datetime, *, gap: tuple[datetime, datetime] | None
) -> None:
    """A heartbeat every five minutes from 08:00 to 18:00, save for the hours of ``gap``."""
    opens = day.replace(hour=8, minute=0)
    moment = opens
    while moment <= day.replace(hour=18, minute=0):
        if gap is None or not gap[0] <= moment < gap[1]:
            session.add(Heartbeat(device_id=device.id, ts=moment, online=True))
        moment += timedelta(minutes=5)
    await session.flush()


async def test_availability_counts_a_reported_outage_inside_working_hours_only(
    session: AsyncSession,
) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    line = await line_of(session, school)
    day = WORKDAY.replace(hour=0, minute=0)
    await heartbeats_of_the_working_day(session, device, day, gap=None)
    session.add_all(
        [
            Outage(
                device_id=device.id,
                line_id=line.id,
                started_at=day.replace(hour=10),
                ended_at=day.replace(hour=11),
            ),
            # Night-time downtime is invisible: the school is closed (ADR-014).
            Outage(
                device_id=device.id,
                line_id=line.id,
                started_at=day.replace(hour=19),
                ended_at=day.replace(hour=20),
            ),
        ]
    )
    await session.flush()

    result = await school_availability(session, school.id, start=day, end=day + timedelta(days=1))

    assert result.observed_s == 10 * 3600
    assert result.downtime_s == 3600
    assert result.uptime_pct == 90


async def test_availability_counts_silence_longer_than_the_threshold(
    session: AsyncSession,
) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    day = WORKDAY.replace(hour=0, minute=0)
    await heartbeats_of_the_working_day(
        session, device, day, gap=(day.replace(hour=10), day.replace(hour=11))
    )

    result = await school_availability(session, school.id, start=day, end=day + timedelta(days=1))

    # The last heartbeat before the gap (09:55) vouches for 15 minutes more, so the school
    # counts as down from 10:10 until the next one at 11:00 — 50 minutes.
    assert result.downtime_s == 50 * 60
    assert result.uptime_pct == 100 * (1 - 50 * 60 / (10 * 3600))


async def test_a_school_nobody_watched_gets_no_number(session: AsyncSession) -> None:
    await create_settings(session)
    school = await create_school(session)
    await register_device(session, await primary_point(session, school))
    day = WORKDAY.replace(hour=0, minute=0)

    silent = await school_availability(session, school.id, start=day, end=day + timedelta(days=1))
    sunday = day + timedelta(days=2)
    closed = await school_availability(
        session, school.id, start=sunday, end=sunday + timedelta(days=1)
    )

    # Neither heartbeats nor outages: «нет данных», not «лежало» — and Sunday is not observed.
    assert (silent.uptime_pct, silent.observed_s) == (None, 10 * 3600)
    assert (closed.uptime_pct, closed.observed_s) == (None, 0)


async def test_availability_ignores_the_moments_outside_the_period(session: AsyncSession) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    day = WORKDAY.replace(hour=0, minute=0)
    await heartbeats_of_the_working_day(session, device, day, gap=None)

    half = await school_availability(
        session, school.id, start=day.replace(hour=12), end=day.replace(hour=18)
    )

    # Only 12:00–18:00 of the working day is observed, and it was covered end to end.
    assert (half.observed_s, half.downtime_s) == (6 * 3600, 0)
    assert half.uptime_pct == 100


async def test_availability_is_counted_in_utc_storage(session: AsyncSession) -> None:
    await create_settings(session)
    school = await create_school(session)
    device, _ = await register_device(session, await primary_point(session, school))
    day = WORKDAY.replace(hour=0, minute=0)
    await heartbeats_of_the_working_day(session, device, day, gap=None)

    # The same period asked for in UTC gives the same answer: the zone lives in the settings,
    # not in the caller (ADR-014).
    in_utc = await school_availability(
        session,
        school.id,
        start=day.astimezone(UTC),
        end=(day + timedelta(days=1)).astimezone(UTC),
    )

    assert (in_utc.observed_s, in_utc.uptime_pct) == (10 * 3600, 100)
