"""Threshold profiles, schedules and system settings of the admin panel (T-37; ТЗ п. 11, п. 20).

Nothing here is ever deleted: a profile or a schedule is switched off with ``is_active`` and the
next one of its chain applies (ADR-004); the global ones cannot be switched off. Agents get every
change with the next ``GET /api/agent/config``, whose ETag is the hash of its content (T-17), and
measurements keep the thresholds they were judged by (``thresholds_snapshot``), so a change never
rewrites history. The changed fields are returned for the audit record (``describe_action``).
"""

from typing import Any

from sqlalchemy import Select, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import Line, Provider, Region, Schedule, School, ThresholdProfile
from app.schemas.schedules import (
    ScheduleCreate,
    ScheduleDetail,
    ScheduleDetailPage,
    ScheduleScope,
    ScheduleUpdate,
)
from app.schemas.settings import SettingsDetail, SettingsUpdate
from app.schemas.threshold_profiles import (
    ThresholdProfileCreate,
    ThresholdProfileDetail,
    ThresholdProfileDetailPage,
    ThresholdProfileScope,
    ThresholdProfileUpdate,
)
from app.services.references import Changes, apply_changes, ensure_region, invalid_field, page_of
from app.services.settings import system_settings

# Order of the lists: the global row first, then the districts, then lines or schools.
SCOPE_ORDER = {"global": 0, "district": 1, "line": 2, "school": 2}


# --- Threshold profiles --------------------------------------------------------------------


def profile_rows() -> Select[Any]:
    """Profiles with the names of their district, or of the school and provider of their line."""
    return (
        select(
            ThresholdProfile,
            Region.name.label("region_name"),
            School.id.label("school_id"),
            School.full_name.label("school_name"),
            Provider.name.label("provider_name"),
            Line.status.label("line_status"),
        )
        .outerjoin(Region, Region.id == ThresholdProfile.region_id)
        .outerjoin(Line, Line.id == ThresholdProfile.line_id)
        .outerjoin(School, School.id == Line.school_id)
        .outerjoin(Provider, Provider.id == Line.provider_id)
    )


def profile_detail(row: Any) -> ThresholdProfileDetail:
    profile: ThresholdProfile = row.ThresholdProfile
    return ThresholdProfileDetail.model_validate(
        {
            "id": profile.id,
            "scope": profile.scope,
            "region_id": profile.region_id,
            "region_name": row.region_name,
            "line_id": profile.line_id,
            "school_id": row.school_id,
            "school_name": row.school_name,
            "provider_name": row.provider_name,
            "line_status": row.line_status,
            "thresholds": {
                "download_min_mbps": profile.download_min_mbps,
                "upload_min_mbps": profile.upload_min_mbps,
                "ping_max_ms": profile.ping_max_ms,
                "jitter_max_ms": profile.jitter_max_ms,
                "packet_loss_max_pct": profile.packet_loss_max_pct,
            },
            "unstable_deviation_pct": profile.unstable_deviation_pct,
            "is_active": profile.is_active,
        }
    )


async def threshold_profile_detail(
    session: AsyncSession, profile_id: int
) -> ThresholdProfileDetail:
    row = (
        await session.execute(profile_rows().where(ThresholdProfile.id == profile_id))
    ).one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Профиль порогов не найден")
    return profile_detail(row)


async def threshold_profile_list(
    session: AsyncSession, params: PageParams, scope: ThresholdProfileScope | None
) -> ThresholdProfileDetailPage:
    query = profile_rows().order_by(
        case(SCOPE_ORDER, value=ThresholdProfile.scope),
        Region.name,
        School.full_name,
        ThresholdProfile.id,
    )
    if scope is not None:
        query = query.where(ThresholdProfile.scope == scope)
    rows, total = await page_of(session, query, params)
    return ThresholdProfileDetailPage(
        items=[profile_detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_threshold_profile(
    session: AsyncSession, body: ThresholdProfileCreate
) -> ThresholdProfileDetail:
    if body.region_id is not None:
        await ensure_region(session, body.region_id)
    if body.line_id is not None and await session.get(Line, body.line_id) is None:
        raise invalid_field("line_id", "Линия не найдена")
    taken = await session.scalar(
        select(ThresholdProfile.id).where(
            ThresholdProfile.scope == body.scope,
            ThresholdProfile.region_id.is_not_distinct_from(body.region_id),
            ThresholdProfile.line_id.is_not_distinct_from(body.line_id),
        )
    )
    if taken is not None:
        raise ApiError(
            409,
            "threshold_profile_exists",
            "У этой цели уже есть профиль порогов — измените или включите его",
        )
    profile = ThresholdProfile(
        scope=body.scope,
        region_id=body.region_id,
        line_id=body.line_id,
        unstable_deviation_pct=body.unstable_deviation_pct,
        **body.thresholds.model_dump(),
    )
    session.add(profile)
    await session.commit()
    return await threshold_profile_detail(session, profile.id)


async def update_threshold_profile(
    session: AsyncSession, profile_id: int, body: ThresholdProfileUpdate
) -> tuple[ThresholdProfileDetail, Changes]:
    profile = await session.get(ThresholdProfile, profile_id)
    if profile is None:
        raise ApiError(404, "not_found", "Профиль порогов не найден")
    if profile.scope == "global" and body.is_active is False:
        raise ApiError(
            409,
            "global_threshold_profile_required",
            "Глобальный профиль порогов нельзя отключить: он действует, когда других нет",
        )
    updates = body.model_dump(exclude_unset=True, exclude={"thresholds"})
    if body.thresholds is not None:
        updates.update(body.thresholds.model_dump())
    changes = apply_changes(profile, updates)
    await session.commit()
    return await threshold_profile_detail(session, profile_id), changes


# --- Schedules -----------------------------------------------------------------------------


def schedule_rows() -> Select[Any]:
    """Schedules with the names of their district or school."""
    return (
        select(
            Schedule,
            Region.name.label("region_name"),
            School.full_name.label("school_name"),
        )
        .outerjoin(Region, Region.id == Schedule.region_id)
        .outerjoin(School, School.id == Schedule.school_id)
    )


def schedule_detail(row: Any) -> ScheduleDetail:
    schedule: Schedule = row.Schedule
    return ScheduleDetail.model_validate(
        {
            "id": schedule.id,
            "scope": schedule.scope,
            "region_id": schedule.region_id,
            "region_name": row.region_name,
            "school_id": schedule.school_id,
            "school_name": row.school_name,
            "slots": schedule.slots,
            "is_active": schedule.is_active,
        }
    )


async def one_schedule(session: AsyncSession, schedule_id: int) -> ScheduleDetail:
    row = (await session.execute(schedule_rows().where(Schedule.id == schedule_id))).one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Расписание не найдено")
    return schedule_detail(row)


async def schedule_list(
    session: AsyncSession, params: PageParams, scope: ScheduleScope | None
) -> ScheduleDetailPage:
    query = schedule_rows().order_by(
        case(SCOPE_ORDER, value=Schedule.scope), Region.name, School.full_name, Schedule.id
    )
    if scope is not None:
        query = query.where(Schedule.scope == scope)
    rows, total = await page_of(session, query, params)
    return ScheduleDetailPage(
        items=[schedule_detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_schedule(session: AsyncSession, body: ScheduleCreate) -> ScheduleDetail:
    if body.region_id is not None:
        await ensure_region(session, body.region_id)
    if body.school_id is not None and await session.get(School, body.school_id) is None:
        raise invalid_field("school_id", "Школа не найдена")
    taken = await session.scalar(
        select(Schedule.id).where(
            Schedule.scope == body.scope,
            Schedule.region_id.is_not_distinct_from(body.region_id),
            Schedule.school_id.is_not_distinct_from(body.school_id),
        )
    )
    if taken is not None:
        raise ApiError(
            409, "schedule_exists", "У этой цели уже есть расписание — измените или включите его"
        )
    schedule = Schedule(
        scope=body.scope,
        region_id=body.region_id,
        school_id=body.school_id,
        slots=[slot.model_dump(mode="json") for slot in body.slots],
    )
    session.add(schedule)
    await session.commit()
    return await one_schedule(session, schedule.id)


async def update_schedule(
    session: AsyncSession, schedule_id: int, body: ScheduleUpdate
) -> tuple[ScheduleDetail, Changes]:
    schedule = await session.get(Schedule, schedule_id)
    if schedule is None:
        raise ApiError(404, "not_found", "Расписание не найдено")
    if schedule.scope == "global" and body.is_active is False:
        raise ApiError(
            409,
            "global_schedule_required",
            "Глобальное расписание нельзя отключить: оно действует, когда других нет",
        )
    changes = apply_changes(schedule, body.model_dump(mode="json", exclude_unset=True))
    await session.commit()
    return await one_schedule(session, schedule_id), changes


# --- System settings -----------------------------------------------------------------------


async def settings_detail(session: AsyncSession) -> SettingsDetail:
    settings = await system_settings(session)
    return SettingsDetail.model_validate(
        {
            "speedtest": {"librespeed_url": settings.librespeed_url, "ndt7_url": settings.ndt7_url},
            "heartbeat_interval_s": settings.heartbeat_interval_s,
            "config_refresh_interval_s": settings.config_refresh_interval_s,
            "offline_after_s": settings.offline_after_s,
            "school_status_measurements_count": settings.school_status_measurements_count,
            "default_working_hours": settings.default_working_hours,
            "availability_min_pct": settings.availability_min_pct,
            "contract_mismatch_threshold_pct": settings.contract_mismatch_threshold_pct,
            "contract_mismatch_window_days": settings.contract_mismatch_window_days,
            "enrollment_code_ttl_days": settings.enrollment_code_ttl_days,
            "export_sync_max_rows": settings.export_sync_max_rows,
            "export_retention_days": settings.export_retention_days,
            "incident_auto_close_hours": settings.incident_auto_close_hours,
        }
    )


async def update_settings(
    session: AsyncSession, body: SettingsUpdate
) -> tuple[SettingsDetail, Changes]:
    settings = await system_settings(session)
    updates = body.model_dump(mode="json", exclude_unset=True, exclude={"speedtest"})
    if body.speedtest is not None:
        updates.update(body.speedtest.model_dump())
    heartbeat = updates.get("heartbeat_interval_s", settings.heartbeat_interval_s)
    if updates.get("offline_after_s", settings.offline_after_s) <= heartbeat:
        raise invalid_field(
            "offline_after_s", "Должно быть больше интервала heartbeat, иначе агент «пропадает»"
        )
    changes = apply_changes(settings, updates)
    await session.commit()
    return await settings_detail(session), changes
