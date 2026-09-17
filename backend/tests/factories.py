"""Rows the API tests start from: a school with a line and a point, codes, devices.

Issuing an installation code and a device token repeats what T-14 and T-36 do in the
application: the secret is generated once, the database keeps only its argon2 hash, and the id
of the row is the part that finds it back (``app/core/security.py``, ADR-005).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    format_device_token,
    format_enrollment_code,
    hash_secret,
    new_device_secret,
    new_enrollment_secret,
)
from app.models import (
    Device,
    EnrollmentCode,
    Line,
    MonitoringPoint,
    Provider,
    Region,
    School,
    SystemSettings,
)

ENROLLMENT_CODE_TTL = timedelta(days=7)


async def create_school(
    session: AsyncSession,
    *,
    school_code: str = "VKO-UK-001",
    room: str | None = "Серверная",
    with_point: bool = True,
) -> School:
    """School with a provider, a main line and, unless ``with_point`` is off, one primary
    monitoring point in ``room``."""
    region = Region(code=school_code, name=f"Район {school_code}")
    provider = Provider(name=f"Провайдер {school_code}")
    session.add_all([region, provider])
    await session.flush()

    school = School(school_code=school_code, full_name=f"Школа {school_code}", region_id=region.id)
    session.add(school)
    await session.flush()

    line = Line(school_id=school.id, provider_id=provider.id, status="main")
    session.add(line)
    await session.flush()

    if with_point:
        session.add(
            MonitoringPoint(
                school_id=school.id, line_id=line.id, name="Точка", room=room, is_primary=True
            )
        )
        await session.flush()
    return school


async def primary_point(session: AsyncSession, school: School) -> MonitoringPoint:
    """Primary monitoring point of the school."""
    return (
        await session.scalars(
            select(MonitoringPoint).where(
                MonitoringPoint.school_id == school.id, MonitoringPoint.is_primary
            )
        )
    ).one()


async def add_point(
    session: AsyncSession, school: School, *, name: str, room: str | None
) -> MonitoringPoint:
    """One more monitoring point of the school, on the line of the primary one."""
    line_id = await session.scalar(
        select(Line.id).where(Line.school_id == school.id).order_by(Line.id).limit(1)
    )
    point = MonitoringPoint(school_id=school.id, line_id=line_id, name=name, room=room)
    session.add(point)
    await session.flush()
    return point


async def issue_enrollment_code(
    session: AsyncSession, school: School, *, expires_in: timedelta = ENROLLMENT_CODE_TTL
) -> str:
    """One-time installation code of the school, as ``POST /api/devices/enrollment-codes`` will
    issue it in T-36: the code is shown once, the row keeps only its hash."""
    secret = new_enrollment_secret()
    entry = EnrollmentCode(
        code_hash=hash_secret(secret),
        school_id=school.id,
        expires_at=datetime.now(UTC) + expires_in,
    )
    session.add(entry)
    await session.flush()
    return format_enrollment_code(entry.id, secret)


async def register_device(
    session: AsyncSession, point: MonitoringPoint, *, device_uid: str = "PC-1"
) -> tuple[Device, str]:
    """Device already bound to ``point``; returns it together with its token."""
    secret = new_device_secret()
    device = Device(
        device_uid=device_uid,
        monitoring_point_id=point.id,
        token_hash=hash_secret(secret),
        agent_version="0.1.0",
    )
    session.add(device)
    await session.flush()
    return device, format_device_token(device.id, secret)


async def create_settings(
    session: AsyncSession,
    *,
    librespeed_url: str = "https://speedtest.example.kz",
    ndt7_url: str | None = None,
) -> SystemSettings:
    """The single row of ``settings`` that ``make seed`` creates on a fresh database (T-05).

    Everything else in it keeps the defaults of the migration, which is what a seeded database
    has too: the intervals of the agent, and later the values of the other tasks (T-17, T-37).
    """
    settings = SystemSettings(id=1, librespeed_url=librespeed_url, ndt7_url=ndt7_url)
    session.add(settings)
    await session.flush()
    # Columns filled by the database defaults are read back, as a fresh session would see them.
    await session.refresh(settings)
    return settings
