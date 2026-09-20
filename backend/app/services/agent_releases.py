"""Agent releases of the admin panel (T-50; ТЗ п. 20; plan.md §4.6): list, publish, change.

A release is an MSI build with its SHA-256: the agent downloads it, checks the hash and refuses
a build that does not match (plan.md §4.6). Version, link and hash are therefore fixed once
published — a fix is a new release — and only the channel and ``is_active`` change afterwards.
A release is never deleted: the hash of a build that is already installed must stay checkable.

The channel decides who gets it: a device on ``pilot`` takes the newest release of either
channel, a device on ``stable`` only a stable one, so promoting a pilot release to ``stable``
is what hands it to the rest. The changed fields are returned for the audit record
(``describe_action``).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import AgentRelease
from app.schemas.agent_releases import (
    AgentChannel,
    AgentReleaseCreate,
    AgentReleaseDetail,
    AgentReleaseDetailPage,
    AgentReleaseUpdate,
)
from app.services.references import Changes, apply_changes, is_taken, page_of

# Channels a device of the key may install; the CHECK of ``devices`` allows no other key.
CHANNELS: dict[str, tuple[AgentChannel, ...]] = {
    "pilot": ("pilot", "stable"),
    "stable": ("stable",),
}


def release_detail(release: AgentRelease) -> AgentReleaseDetail:
    return AgentReleaseDetail.model_validate(release, from_attributes=True)


def release_not_found() -> ApiError:
    return ApiError(404, "not_found", "Релиз агента не найден")


async def agent_release_list(session: AsyncSession, params: PageParams) -> AgentReleaseDetailPage:
    query = select(AgentRelease).order_by(AgentRelease.released_at.desc(), AgentRelease.id.desc())
    rows, total = await page_of(session, query, params)
    return AgentReleaseDetailPage(
        items=[release_detail(row.AgentRelease) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_agent_release(
    session: AsyncSession, body: AgentReleaseCreate
) -> AgentReleaseDetail:
    """Publish a build; a version that is already published is a 409, even if withdrawn."""
    if await is_taken(session, AgentRelease.version, body.version, None):
        raise ApiError(409, "release_version_taken", "Релиз с этой версией уже опубликован")
    release = AgentRelease(**body.model_dump())
    session.add(release)
    await session.commit()
    # ``is_active`` and ``released_at`` were set by the database: read them back.
    await session.refresh(release)
    return release_detail(release)


async def update_agent_release(
    session: AsyncSession, release_id: int, body: AgentReleaseUpdate
) -> tuple[AgentReleaseDetail, Changes]:
    """Promote a release to another channel or withdraw it; the build itself never changes."""
    release = await session.get(AgentRelease, release_id)
    if release is None:
        raise release_not_found()
    changes = apply_changes(release, body.model_dump(exclude_unset=True))
    await session.commit()
    return release_detail(release), changes


async def latest_release(session: AsyncSession, channel: str) -> AgentRelease | None:
    """Newest active release a device of ``channel`` may install; ``None`` while there is none.

    A pilot device takes a release of either channel: a build promoted to ``stable`` is newer
    than the pilot one it came from, and a pilot device must not stay behind the rest.
    """
    allowed = CHANNELS[channel]
    return await session.scalar(
        select(AgentRelease)
        .where(AgentRelease.is_active, AgentRelease.channel.in_(allowed))
        .order_by(AgentRelease.released_at.desc(), AgentRelease.id.desc())
        .limit(1)
    )
