"""Measurement schedules of the admin panel (plan.md §10 «Админка»): list, create, change.

There is no DELETE: a schedule is switched off with ``is_active``. Agents get the new slots
with the configuration (T-17). Every change goes to the audit log (T-37).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.errors import Problem
from app.schemas.schedules import (
    ScheduleCreate,
    ScheduleDetail,
    ScheduleDetailPage,
    ScheduleScope,
    ScheduleUpdate,
)
from app.services import config_admin

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
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScheduleDetailPage:
    return await config_admin.schedule_list(session, params, scope)


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
async def create_schedule(
    body: ScheduleCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> ScheduleDetail:
    return await config_admin.create_schedule(session, body)


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
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScheduleDetail:
    schedule, changes = await config_admin.update_schedule(session, schedule_id, body)
    describe_action(request, changes=changes or None)
    return schedule
