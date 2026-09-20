"""Agent release admin API (plan.md §4.6, §10 «Админка», ТЗ п. 20): list, publish, change.

There is no DELETE: a release is withdrawn with ``is_active`` and the hash of a published MSI
stays checkable. Version, link and hash are fixed once published — a fix is a new release — so
only the channel and ``is_active`` change here. Releases are managed by the Administrator role
(ADR-008 «Открыто»); every change goes to the audit log.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.agent_releases import (
    AgentReleaseCreate,
    AgentReleaseDetail,
    AgentReleaseDetailPage,
    AgentReleaseUpdate,
)
from app.schemas.errors import Problem
from app.services import agent_releases

router = APIRouter(
    prefix="/agent-releases",
    tags=["admin"],
    dependencies=[Depends(require("agent_releases:manage"))],
)


@router.get("", summary="Релизы агента, новые сверху")
async def list_agent_releases(
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentReleaseDetailPage:
    return await agent_releases.agent_release_list(session, params)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Опубликовать релиз агента",
    description=(
        "Агенты канала pilot забирают релиз сразу, остальные — после перевода в stable. "
        "Агент сверяет SHA-256 скачанного MSI и отказывается ставить несовпавший файл."
    ),
    responses={
        409: {
            "model": Problem,
            "description": "Релиз с этой версией уже есть (type release_version_taken)",
        },
    },
)
async def create_agent_release(
    body: AgentReleaseCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> AgentReleaseDetail:
    return await agent_releases.create_agent_release(session, body)


@router.patch(
    "/{release_id}",
    summary="Перевести релиз в другой канал или отозвать",
    description=(
        "Версия, ссылка и SHA-256 не меняются: исправление — это новый релиз. Отозванный "
        "релиз (is_active false) агентам больше не выдаётся, уже установленный остаётся."
    ),
    responses={404: {"model": Problem, "description": "Релиз не найден"}},
)
async def update_agent_release(
    release_id: int,
    body: AgentReleaseUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentReleaseDetail:
    release, changes = await agent_releases.update_agent_release(session, release_id, body)
    describe_action(request, changes=changes or None)
    return release
