"""Threshold profiles of the admin panel (plan.md §10 «Админка»): list, create, change.

Contract stubs: every endpoint answers 501 until T-37. There is no DELETE: a profile is switched
off with ``is_active``; measurements keep the thresholds they were evaluated with (ADR-004).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Security, status

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.threshold_profiles import (
    ThresholdProfileCreate,
    ThresholdProfileDetail,
    ThresholdProfileDetailPage,
    ThresholdProfileScope,
    ThresholdProfileUpdate,
)

router = APIRouter(prefix="/thresholds", tags=["admin"], dependencies=[Security(user_token)])

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
) -> ThresholdProfileDetailPage:
    raise not_implemented("T-37")


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
async def create_threshold_profile(body: ThresholdProfileCreate) -> ThresholdProfileDetail:
    raise not_implemented("T-37")


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
    profile_id: int, body: ThresholdProfileUpdate
) -> ThresholdProfileDetail:
    raise not_implemented("T-37")
