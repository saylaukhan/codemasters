"""Rollout of the monitoring (T-69, docs/design/README.md §6.4; DESIGN.md §3.30).

The first question of the customer in the first months: which schools are not connected yet,
which agents are installed but silent, and which computers are behind the current release. The
screen answers it over the same selection of schools as the main one, so «подключена» means
here exactly what it means there — a school with at least one active computer — and the share of
a district agrees with ``GET /api/dashboard/summary`` (T-22, T-60). That is why the selection
comes from ``school_candidates`` and the computers from ``registered_devices`` of
``app/services/overview.py`` instead of a second definition.

Every window is a setting: «на связи» is a signal not older than ``offline_after_s`` (ADR-014),
«молчит» is silence longer than ``rollout_silent_days`` (ТЗ п. 11, п. 20). «Старая версия» is
not a constant either — it is a version the release table of T-50 no longer publishes.

«Назначить обновление» works through the update channel of T-50: ``devices`` keeps no target
version of its own, and an agent installs the newest release its channel allows, so assigning a
version means putting the chosen computers into the channel that delivers it.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import (
    AgentRelease,
    Device,
    EnrollmentCode,
    MonitoringPoint,
    Region,
    School,
    SchoolContact,
    SystemSettings,
)
from app.schemas.agent_releases import AgentChannel
from app.schemas.rollout import (
    AgentUpdateAssign,
    AgentUpdateAssigned,
    RolloutFilter,
    RolloutListCounts,
    RolloutRegionRow,
    RolloutSchoolItem,
    RolloutSchoolPage,
    RolloutSummary,
)
from app.services.agent_releases import latest_release
from app.services.device_card import device_not_found
from app.services.overview import OverviewFilters, school_candidates, schools_in_registry
from app.services.settings import system_settings
from app.services.status import last_signal


@dataclass(frozen=True)
class SchoolRollout:
    """One school of the selection with everything the four lists and the counters need."""

    school_id: int
    school_code: str
    school_name: str
    region_id: int
    region_name: str
    devices_count: int
    devices_alive_count: int
    devices_silent_count: int
    devices_old_version_count: int
    last_seen_at: datetime | None
    code_issued_at: datetime | None
    agent_versions: tuple[str, ...]
    has_contact: bool

    @property
    def connected(self) -> bool:
        """«Подключена»: at least one active computer, as ``GET /api/dashboard/summary`` counts."""
        return self.devices_count > 0


def full_days(since: datetime, now: datetime) -> int:
    """Full days between the two moments, as «не использован 9 дней» counts them."""
    return max((now - since).days, 0)


async def published_versions(session: AsyncSession) -> tuple[str | None, set[str]]:
    """Version of the current stable release and every version that is not behind it (T-50).

    A build released after the stable one — a pilot release the rest of the schools are still
    waiting for — is not an old version either, so the two are answered together. Versions are
    compared as the release table publishes them, without parsing the numbers: what an agent may
    install is decided by the channel and ``released_at``, never by a constant here.
    """
    stable = await latest_release(session, "stable")
    if stable is None:
        return None, set()
    current = await session.scalars(
        select(AgentRelease.version).where(
            AgentRelease.is_active, AgentRelease.released_at >= stable.released_at
        )
    )
    return stable.version, set(current)


def old_version(current: Iterable[str], version: ColumnElement[str | None]) -> ColumnElement[bool]:
    """Condition of a computer that is not on a currently published release (T-50)."""
    versions = list(current)
    if not versions:
        return false()
    return or_(version.is_(None), version.not_in(versions))


def device_signals(*, now: datetime) -> Select[Any]:
    """Active computers of the schools with the moment each of them was last heard at ``now``.

    A row per computer, so the aggregates of ``school_rows`` count plain columns instead of a
    correlated subquery; the computers are the ones ``registered_devices`` of the main screen
    counts, which is why the sum over the schools is its ``devices_count``.
    """
    return (
        select(
            MonitoringPoint.school_id.label("school_id"),
            Device.id.label("device_id"),
            Device.agent_version.label("agent_version"),
            last_signal(now).label("seen"),
        )
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(Device.status == "active")
    )


def school_rows(
    filters: OverviewFilters, *, now: datetime, settings: SystemSettings, current: Iterable[str]
) -> Select[Any]:
    """Every selected school with its computers counted by state, in one query."""
    signals = device_signals(now=now).subquery("signals")
    alive_since = now - timedelta(seconds=settings.offline_after_s)
    silent_before = now - timedelta(days=settings.rollout_silent_days)
    behind = old_version(current, signals.c.agent_version)
    unused_code = (
        select(func.max(EnrollmentCode.created_at))
        .where(
            EnrollmentCode.school_id == School.id,
            EnrollmentCode.used_at.is_(None),
            EnrollmentCode.created_at <= now,
        )
        .scalar_subquery()
    )
    has_contact = select(SchoolContact.id).where(SchoolContact.school_id == School.id).exists()
    return (
        select(
            School.id,
            School.school_code,
            School.full_name,
            School.region_id,
            Region.name.label("region_name"),
            func.count(signals.c.device_id).label("devices_count"),
            func.count(signals.c.device_id)
            .filter(signals.c.seen >= alive_since)
            .label("devices_alive_count"),
            func.count(signals.c.device_id)
            .filter(or_(signals.c.seen.is_(None), signals.c.seen < silent_before))
            .label("devices_silent_count"),
            func.count(signals.c.device_id).filter(behind).label("devices_old_version_count"),
            func.max(signals.c.seen).label("last_seen_at"),
            func.array_agg(func.distinct(signals.c.agent_version)).label("agent_versions"),
            unused_code.label("code_issued_at"),
            has_contact.label("has_contact"),
        )
        .join(Region, Region.id == School.region_id)
        .outerjoin(signals, signals.c.school_id == School.id)
        .where(School.id.in_(school_candidates(filters)))
        .group_by(School.id, Region.name)
        .order_by(School.full_name, School.id)
    )


async def selection(
    session: AsyncSession,
    filters: OverviewFilters,
    *,
    now: datetime,
    settings: SystemSettings,
    current: Iterable[str],
) -> list[SchoolRollout]:
    """Selected schools of the user's scope with their computers counted (ADR-008)."""
    rows = await session.execute(school_rows(filters, now=now, settings=settings, current=current))
    return [
        SchoolRollout(
            school_id=row.id,
            school_code=row.school_code,
            school_name=row.full_name,
            region_id=row.region_id,
            region_name=row.region_name,
            devices_count=row.devices_count,
            devices_alive_count=row.devices_alive_count,
            devices_silent_count=row.devices_silent_count,
            devices_old_version_count=row.devices_old_version_count,
            last_seen_at=row.last_seen_at,
            code_issued_at=row.code_issued_at,
            # The aggregate of an outer join answers {NULL} for a school without computers.
            agent_versions=tuple(sorted(v for v in row.agent_versions if v is not None)),
            has_contact=row.has_contact,
        )
        for row in rows
    ]


def matches(school: SchoolRollout, wanted: RolloutFilter, *, silent_before: datetime) -> bool:
    """Whether the school belongs to one of the four lists of §6.4."""
    if wanted == "not_connected":
        return not school.connected
    if wanted == "silent":
        return school.connected and (
            school.last_seen_at is None or school.last_seen_at < silent_before
        )
    if wanted == "code_unused":
        return school.code_issued_at is not None
    return school.devices_old_version_count > 0


# What «худшие сверху» means in each list: the longest silence, the oldest unused code, the name.
ORDER: dict[RolloutFilter, Callable[[SchoolRollout], tuple[Any, ...]]] = {
    "not_connected": lambda school: (school.school_name, school.school_id),
    "silent": lambda school: (
        school.last_seen_at is not None,
        school.last_seen_at or datetime.min,
        school.school_name,
    ),
    "code_unused": lambda school: (school.code_issued_at or datetime.min, school.school_name),
    "old_version": lambda school: (
        -school.devices_old_version_count,
        school.school_name,
        school.school_id,
    ),
}


def counts_of(schools: Sequence[SchoolRollout]) -> dict[str, Any]:
    """The progress numbers over a selection: the fields of ``RolloutCounts``."""
    connected = sum(1 for school in schools if school.connected)
    return {
        "schools_count": len(schools),
        "schools_connected_count": connected,
        "connected_pct": round(100 * connected / len(schools), 1) if schools else 0.0,
        "devices_count": sum(school.devices_count for school in schools),
        "devices_alive_count": sum(school.devices_alive_count for school in schools),
        "devices_silent_count": sum(school.devices_silent_count for school in schools),
        "devices_old_version_count": sum(school.devices_old_version_count for school in schools),
    }


def region_rows(schools: Sequence[SchoolRollout]) -> list[RolloutRegionRow]:
    """«По районам и городам»: the same numbers per district, by name."""
    by_region: dict[tuple[int, str], list[SchoolRollout]] = {}
    for school in schools:
        by_region.setdefault((school.region_id, school.region_name), []).append(school)
    return [
        RolloutRegionRow.model_validate(
            {"region_id": region_id, "region_name": name, **counts_of(rows)}
        )
        for (region_id, name), rows in sorted(by_region.items(), key=lambda item: item[0][1])
    ]


async def rollout_summary(
    session: AsyncSession, filters: OverviewFilters, *, now: datetime
) -> RolloutSummary:
    """Numbers of «Внедрение»: the oblast, its districts and the sizes of the four lists."""
    settings = await system_settings(session)
    target_version, current = await published_versions(session)
    schools = await selection(session, filters, now=now, settings=settings, current=current)
    silent_before = now - timedelta(days=settings.rollout_silent_days)
    return RolloutSummary.model_validate(
        {
            "as_of": now,
            "schools_total_count": await schools_in_registry(session, filters),
            "target_version": target_version,
            "silent_days": settings.rollout_silent_days,
            "alive_after_s": settings.offline_after_s,
            "lists": RolloutListCounts(
                not_connected=sum(
                    1
                    for school in schools
                    if matches(school, "not_connected", silent_before=silent_before)
                ),
                silent=sum(
                    1
                    for school in schools
                    if matches(school, "silent", silent_before=silent_before)
                ),
                code_unused=sum(
                    1
                    for school in schools
                    if matches(school, "code_unused", silent_before=silent_before)
                ),
                old_version=sum(
                    1
                    for school in schools
                    if matches(school, "old_version", silent_before=silent_before)
                ),
            ),
            "regions": region_rows(schools),
            **counts_of(schools),
        }
    )


def school_item(
    school: SchoolRollout, *, now: datetime, silent_before: datetime
) -> RolloutSchoolItem:
    """Row of a list: the school and the fact that put it there (§6.4)."""
    silent = school.connected and (
        school.last_seen_at is None or school.last_seen_at < silent_before
    )
    return RolloutSchoolItem(
        school_id=school.school_id,
        school_code=school.school_code,
        school_name=school.school_name,
        region_id=school.region_id,
        region_name=school.region_name,
        devices_count=school.devices_count,
        devices_alive_count=school.devices_alive_count,
        last_seen_at=school.last_seen_at,
        silent_days=(
            full_days(school.last_seen_at, now)
            if silent and school.last_seen_at is not None
            else None
        ),
        code_issued_at=school.code_issued_at,
        code_age_days=(
            full_days(school.code_issued_at, now) if school.code_issued_at is not None else None
        ),
        agent_versions=list(school.agent_versions),
        has_contact=school.has_contact,
    )


async def rollout_schools(
    session: AsyncSession,
    filters: OverviewFilters,
    *,
    wanted: RolloutFilter,
    now: datetime,
    limit: int,
) -> RolloutSchoolPage:
    """One of the four lists of §6.4, the worst first; ``total`` counts it before ``limit``."""
    settings = await system_settings(session)
    target_version, current = await published_versions(session)
    schools = await selection(session, filters, now=now, settings=settings, current=current)
    silent_before = now - timedelta(days=settings.rollout_silent_days)
    picked = sorted(
        (school for school in schools if matches(school, wanted, silent_before=silent_before)),
        key=ORDER[wanted],
    )
    return RolloutSchoolPage(
        as_of=now,
        filter=wanted,
        target_version=target_version,
        silent_days=settings.rollout_silent_days,
        total=len(picked),
        items=[
            school_item(school, now=now, silent_before=silent_before) for school in picked[:limit]
        ],
    )


def delivering_channel(release: AgentRelease) -> AgentChannel:
    """Channel whose agents install ``release``: a pilot build reaches pilot computers only."""
    return "pilot" if release.channel == "pilot" else "stable"


async def assign_agent_update(
    session: AsyncSession, body: AgentUpdateAssign
) -> AgentUpdateAssigned:
    """Put the chosen computers, or a whole district, into the channel that gives ``version``.

    ``devices`` has no target version of its own: an agent installs the newest release its
    channel allows (T-50), so only the newest release of a channel can be a target — an older
    one is a 409, not a silent no-op. A computer outside the scope of the user is not seen
    (ADR-008), and a request that names only such computers is a 404, as in ``devices.py``.
    """
    release = await session.scalar(
        select(AgentRelease).where(AgentRelease.version == body.version, AgentRelease.is_active)
    )
    if release is None:
        raise ApiError(404, "not_found", "Активный релиз агента с этой версией не найден")
    channel = delivering_channel(release)
    latest = await latest_release(session, channel)
    if latest is None or latest.version != release.version:
        raise ApiError(
            409,
            "release_not_latest",
            "Агент ставит последний релиз своего канала: целевой версией может быть только он",
        )

    query = (
        select(Device)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(
            Device.status == "active",
            MonitoringPoint.school_id.in_(school_candidates(OverviewFilters(body.region_id))),
        )
    )
    if body.device_ids is not None:
        query = query.where(Device.id.in_(body.device_ids))
    devices = list(await session.scalars(query))
    if body.device_ids is not None and not devices:
        raise device_not_found()

    changed = [device for device in devices if device.update_channel != channel]
    for device in changed:
        device.update_channel = channel
    await session.commit()
    return AgentUpdateAssigned(
        version=release.version,
        channel=channel,
        devices_count=len(devices),
        devices_changed_count=len(changed),
    )
