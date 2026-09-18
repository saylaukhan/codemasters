"""Measurement schedules of the admin panel (plan.md §10 «Админка»): list, create, change.

Contract stubs: every endpoint answers 501 until T-37. There is no DELETE: a schedule is
switched off with ``is_active``. Agents get the new slots with the configuration (T-17).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.auth import require
from app.core.deps import PageParams, page_params
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.schedules import (
    ScheduleCreate,
    ScheduleDetail,
    ScheduleDetailPage,
    ScheduleScope,
    ScheduleUpdate,
)

router = APIRouter(
    prefix="/schedules", tags=["admin"], dependencies=[Depends(require("schedules:manage"))]
)

SCHEDULE_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Расписание не найдено"}


@router.get(
    "",
    summary="Расписания замеров: глобальное, районов, школ",
    description=(
        "Порядок: глобальное, районы по region_name, школы по school_name. Агент получает самое "
        "конкретное активное расписание: школа → район → глобальное."
    ),
)
async def list_schedules(
    params: Annotated[PageParams, Depends(page_params)],
    scope: ScheduleScope | None = None,
) -> ScheduleDetailPage:
    raise not_implemented("T-37")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать расписание района или школы",
    description="Пересекающиеся слоты — 422. Неизвестный region_id или school_id — 422.",
    responses={
        409: {
            "model": Problem,
            "description": "У этой цели уже есть расписание, в том числе отключённое "
            "(type schedule_exists)",
        },
    },
)
async def create_schedule(body: ScheduleCreate) -> ScheduleDetail:
    raise not_implemented("T-37")


@router.patch(
    "/{schedule_id}",
    summary="Изменить слоты или отключить расписание",
    description="Пересекающиеся слоты — 422.",
    responses={
        404: SCHEDULE_NOT_FOUND,
        409: {
            "model": Problem,
            "description": "Глобальное расписание нельзя отключить (type global_schedule_required)",
        },
    },
)
async def update_schedule(schedule_id: int, body: ScheduleUpdate) -> ScheduleDetail:
    raise not_implemented("T-37")
