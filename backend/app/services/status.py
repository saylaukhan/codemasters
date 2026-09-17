"""Status of a school on the map and in lists: measurements plus heartbeat (ADR-004, T-16).

The status of a single measurement is evaluated on receipt (T-18); here the last ones of the
main line are folded into the status of the school, and a silent agent overrides them: no
heartbeat for longer than ``offline_after_s`` in working hours means «Нет соединения», outside
them «Нет данных» — a computer switched off for the night is not a broken line (ADR-014).
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Line, Measurement, MonitoringPoint
from app.schemas.schools import WorkingHours
from app.schemas.statuses import SchoolStatus
from app.services.settings import system_settings
from app.services.working_hours import is_working_time

# Statuses of a measurement from the mildest to the worst (ADR-004).
SEVERITY: tuple[SchoolStatus, ...] = ("normal", "unstable", "critical", "offline")

# Wi-Fi does not rate the line: the air, not the provider, is measured through it (ADR-012).
WIFI = "wifi"


def worst_of_the_majority(statuses: Sequence[str]) -> SchoolStatus:
    """Fold the last measurements into one status: the median of them by severity.

    The rule of this task (ТЗ п. 13, ADR-004: N = 3 by default): a single deviation among the
    last N does not colour the school, two of three do. With fewer measurements than N the
    median of what there is answers, so one measurement speaks for itself.
    """
    ranked = sorted(SEVERITY.index(status) for status in statuses)
    return SEVERITY[ranked[len(ranked) // 2]]


async def school_status(session: AsyncSession, school_id: int, *, now: datetime) -> SchoolStatus:
    """Status of the school at ``now``: «Нет данных» while nothing has been measured yet.

    Only the main line counts and only measurements that are not made over Wi-Fi: the reserve
    line and the air are not what the school is judged by (ADR-004, ADR-012).
    """
    settings = await system_settings(session)
    hours = WorkingHours.model_validate(settings.default_working_hours)

    last_seen = await session.scalar(
        select(func.max(Device.last_seen_at))
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(MonitoringPoint.school_id == school_id, Device.status == "active")
    )
    if last_seen is None or now - last_seen > timedelta(seconds=settings.offline_after_s):
        return "offline" if is_working_time(hours, settings.timezone, now) else "no_data"

    latest = await session.scalars(
        select(Measurement.quality_status)
        .join(Line, Line.id == Measurement.line_id)
        .where(
            Line.school_id == school_id,
            Line.status == "main",
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.quality_status.is_not(None),
        )
        .order_by(Measurement.measured_at.desc())
        .limit(settings.school_status_measurements_count)
    )
    # Measurements received before T-18 carry no status of their own and say nothing here.
    statuses = [status for status in latest if status is not None]
    if not statuses:
        return "no_data"
    return worst_of_the_majority(statuses)
