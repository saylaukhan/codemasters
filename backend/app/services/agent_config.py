"""Configuration an agent asks for: schedule, thresholds, servers, version (T-17, ADR-012).

Nothing here is hard-coded in the agent: the answer is assembled from the database along the
chain device → line → district → global settings (ТЗ п. 11, п. 20; ADR-004). ``latest_version``
follows the update channel of the device, as ``GET /api/agent/releases/latest`` does (T-50).
The ETag is the hash of that answer, so any change of ``schedules``, ``threshold_profiles``,
``settings`` or ``agent_releases`` gives the agent a new configuration and everything else
costs it a 304.
"""

import hashlib

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import Device, MonitoringPoint, Schedule, School
from app.schemas.agent import AgentConfigResponse, ScheduleSlot, SpeedtestServers
from app.schemas.thresholds import ThresholdValues
from app.services.agent_releases import latest_release
from app.services.settings import NOT_CONFIGURED, NOT_CONFIGURED_DETAIL, system_settings
from app.services.thresholds import most_specific, threshold_profile


async def agent_config(session: AsyncSession, device: Device) -> AgentConfigResponse:
    """Build the configuration of ``device`` (ТЗ п. 2, п. 11, п. 20).

    The school and the line come from the monitoring point of the device, never from the
    request (ТЗ п. 12, ADR-005); a missing settings row, schedule or threshold profile is an
    incomplete installation, not a bad request, so it answers 503.
    """
    target = (
        await session.execute(
            select(MonitoringPoint.school_id, MonitoringPoint.line_id, School.region_id)
            .join(School, School.id == MonitoringPoint.school_id)
            .where(MonitoringPoint.id == device.monitoring_point_id)
        )
    ).one()

    settings = await system_settings(session)
    schedule = await session.scalar(
        most_specific(
            select(Schedule).where(
                Schedule.is_active,
                or_(
                    Schedule.scope == "global",
                    (Schedule.scope == "district") & (Schedule.region_id == target.region_id),
                    (Schedule.scope == "school") & (Schedule.school_id == target.school_id),
                ),
            ),
            ["school", "district", "global"],
            Schedule.scope,
        )
    )
    # The agent is told the thresholds of its line so that it can show them, never judge by
    # them: the status of a measurement is the server's (ADR-004, T-18).
    profile = await threshold_profile(session, line_id=target.line_id, region_id=target.region_id)
    if schedule is None or profile is None:
        raise ApiError(503, NOT_CONFIGURED, NOT_CONFIGURED_DETAIL)

    return AgentConfigResponse(
        # Slots are local times of the zone of the schedule; storage stays UTC (ADR-014).
        timezone=schedule.timezone,
        schedule_slots=[ScheduleSlot.model_validate(slot) for slot in schedule.slots],
        heartbeat_interval_s=settings.heartbeat_interval_s,
        config_refresh_interval_s=settings.config_refresh_interval_s,
        speedtest=SpeedtestServers(
            librespeed_url=settings.librespeed_url, ndt7_url=settings.ndt7_url
        ),
        thresholds=ThresholdValues(
            download_min_mbps=profile.download_min_mbps,
            upload_min_mbps=profile.upload_min_mbps,
            ping_max_ms=profile.ping_max_ms,
            jitter_max_ms=profile.jitter_max_ms,
            packet_loss_max_pct=profile.packet_loss_max_pct,
        ),
        latest_version=await latest_version(session, device),
        token_rotation_required=device.token_rotation_requested_at is not None,
    )


async def latest_version(session: AsyncSession, device: Device) -> str | None:
    """Version of the newest published release the agent may update to; ``None`` while none is.

    The release is the one of the channel of the device, so a promotion to ``stable`` or a
    withdrawal changes the answer and its ETag for exactly the agents it concerns (T-50).
    """
    release = await latest_release(session, device.update_channel)
    return release.version if release is not None else None


def config_etag(config: AgentConfigResponse) -> str:
    """Strong ETag of the configuration: its content hashed, quoted as RFC 9110 requires."""
    digest = hashlib.sha256(config.model_dump_json().encode()).hexdigest()
    return f'"{digest[:32]}"'


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """Whether ``If-None-Match`` already holds ``etag``; weak tags compare by their value."""
    if not if_none_match:
        return False
    tags = [tag.strip() for tag in if_none_match.split(",")]
    return "*" in tags or any(tag.removeprefix("W/") == etag for tag in tags)
