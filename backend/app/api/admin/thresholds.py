"""Threshold profiles of the admin panel (plan.md §10 «Админка»): list, create, change.

There is no DELETE: a profile is switched off with ``is_active``; measurements keep the
thresholds they were evaluated with (ADR-004). Every change goes to the audit log (T-37).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.errors import Problem
from app.schemas.threshold_profiles import (
    ThresholdProfileCreate,
    ThresholdProfileDetail,
    ThresholdProfileDetailPage,
    ThresholdProfileScope,
    ThresholdProfileUpdate,
)
from app.services import config_admin

router = APIRouter(
    prefix="/thresholds", tags=["admin"], dependencies=[Depends(require("thresholds:manage"))]
)

PROFILE_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Профиль порогов не найден"}


@router.get(
    "",
    summary="Профили порогов: глобальный, районов, линий",
    description=(
        "Порядок: глобальный, районы по region_name, линии по school_name. Замер оценивает самый "
        "конкретный активный профиль: линия → район → глобальный (ADR-004)."
    ),
)
async def list_threshold_profiles(
    params: Annotated[PageParams, Depends(page_params)],
    scope: ThresholdProfileScope | None = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ThresholdProfileDetailPage:
    return await config_admin.threshold_profile_list(session, params, scope)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать профиль порогов района или линии",
    description="Действует со следующего замера. Неизвестный region_id или line_id — 422.",
    responses={
        409: {
            "model": Problem,
            "description": "У этой цели уже есть профиль, в том числе отключённый "
            "(type threshold_profile_exists)",
        },
    },
)
async def create_threshold_profile(
    body: ThresholdProfileCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> ThresholdProfileDetail:
    return await config_admin.create_threshold_profile(session, body)


@router.patch(
    "/{profile_id}",
    summary="Изменить или отключить профиль порогов",
    description="Уже сохранённые замеры не пересчитываются: у каждого свой снимок порогов.",
    responses={
        404: PROFILE_NOT_FOUND,
        409: {
            "model": Problem,
            "description": "Глобальный профиль нельзя отключить "
            "(type global_threshold_profile_required)",
        },
    },
)
async def update_threshold_profile(
    profile_id: int,
    body: ThresholdProfileUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ThresholdProfileDetail:
    profile, changes = await config_admin.update_threshold_profile(session, profile_id, body)
    describe_action(request, changes=changes or None)
    return profile
