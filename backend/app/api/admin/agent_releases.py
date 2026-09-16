"""Agent release admin API (plan.md §4.6, §10 «Админка», ТЗ п. 20): list, publish, change.

Contract stubs: every endpoint answers 501 until T-50. There is no DELETE: a release is
withdrawn with ``is_active``. Releases are managed by the Administrator role (ADR-008 «Открыто»).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.agent_releases import (
    AgentReleaseCreate,
    AgentReleaseDetail,
    AgentReleaseDetailPage,
    AgentReleaseUpdate,
)
from app.schemas.errors import Problem

router = APIRouter(prefix="/agent-releases", tags=["admin"], dependencies=[Security(user_token)])


@router.get("", summary="Релизы агента, новые сверху")
async def list_agent_releases(
    params: Annotated[PageParams, Depends(page_params)],
) -> AgentReleaseDetailPage:
    raise not_implemented("T-50")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Опубликовать релиз агента",
    responses={
        409: {
            "model": Problem,
            "description": "Релиз с этой версией уже есть (type release_version_taken)",
        },
    },
)
async def create_agent_release(body: AgentReleaseCreate) -> AgentReleaseDetail:
    raise not_implemented("T-50")


@router.patch(
    "/{release_id}",
    summary="Перевести релиз в другой канал или отозвать",
    responses={404: {"model": Problem, "description": "Релиз не найден"}},
)
async def update_agent_release(release_id: int, body: AgentReleaseUpdate) -> AgentReleaseDetail:
    raise not_implemented("T-50")
