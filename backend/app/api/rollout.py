"""Rollout API (T-69, docs/design/README.md §6.4; DESIGN.md §3.30): who is not connected yet.

The numbers are the ones of the main screen over the same schools, so the share of connected
schools of a district agrees with ``GET /api/dashboard/summary`` (T-22). Reading the screen asks
for ``devices:read`` — it is a view of the computers of the oblast, limited by the scope of the
user (ADR-008), and the navigation of a cabinet does not offer the section at all
(``web/src/app/sections.ts``). Changing the update channel of a computer asks for
``devices:manage``, as every other change of a device does (T-36).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.schemas.errors import Problem
from app.schemas.rollout import (
    AgentUpdateAssign,
    AgentUpdateAssigned,
    RolloutFilter,
    RolloutSchoolPage,
    RolloutSummary,
)
from app.services.overview import OverviewFilters
from app.services.rollout import assign_agent_update, rollout_schools, rollout_summary

router = APIRouter(
    prefix="/rollout", tags=["rollout"], dependencies=[Depends(require("devices:read"))]
)


@router.get(
    "/summary",
    summary="Ход внедрения: подключённые школы, компьютеры на связи, районы",
    description=(
        "«Подключена» — у школы есть хотя бы один активный компьютер, как считает "
        "GET /api/dashboard/summary: schools_count и devices_count совпадают с его числами по "
        "тем же фильтрам. «На связи» — сигнал не старше offline_after_s, «молчит» — тишина "
        "дольше rollout_silent_days, «старая версия» — версия, которой нет среди действующих "
        "релизов канала stable и новее (T-50). Все окна берутся из настроек (ТЗ п. 20). "
        "schools_total_count включает отключённые школы, lists — размеры четырёх списков."
    ),
)
async def get_rollout_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    region_id: int | None = None,
    as_of: Annotated[
        AwareDatetime | None,
        Query(description="Момент, на который собираются числа; по умолчанию — текущий"),
    ] = None,
) -> RolloutSummary:
    return await rollout_summary(
        session, OverviewFilters(region_id), now=as_of or datetime.now(UTC)
    )


@router.get(
    "/schools",
    summary="Школы одного из четырёх списков внедрения",
    description=(
        "filter выбирает критерий (docs/design/README.md §6.4): not_connected — нет ни одного "
        "активного компьютера; silent — компьютер есть, но последний heartbeat старше "
        "rollout_silent_days; code_unused — код установки выдан и не использован, с его "
        "возрастом; old_version — есть компьютер не на действующем релизе агента. Порядок — "
        "худшие сверху: самая долгая тишина, самый старый код, больше всего устаревших "
        "компьютеров. total считается до ограничения limit, для подписи «Ещё N школ»."
    ),
)
async def get_rollout_schools(
    session: Annotated[AsyncSession, Depends(get_session)],
    filter: Annotated[RolloutFilter, Query(description="Критерий списка")] = "not_connected",
    region_id: int | None = None,
    as_of: Annotated[
        AwareDatetime | None,
        Query(description="Момент, на который собирается список; по умолчанию — текущий"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Сколько строк вернуть")] = 20,
) -> RolloutSchoolPage:
    return await rollout_schools(
        session,
        OverviewFilters(region_id),
        wanted=filter,
        now=as_of or datetime.now(UTC),
        limit=limit,
    )


@router.post(
    "/devices/agent-update",
    dependencies=[Depends(require("devices:manage"))],
    summary="Назначить обновление: перевести компьютеры в канал целевой версии",
    description=(
        "Целевая версия у устройства не хранится: агент ставит последний релиз своего канала "
        "(T-50), поэтому назначение переводит выбранные компьютеры — или все компьютеры "
        "района — в канал, который выдаёт эту версию. Версия, не являющаяся последней в своём "
        "канале, — 409 release_not_latest: доставить её нечем. Новую версию агенты возьмут при "
        "следующем GET /api/agent/config."
    ),
    responses={
        404: {"model": Problem, "description": "Релиз или устройство не найдены"},
        409: {
            "model": Problem,
            "description": "Версия не последняя в своём канале (type release_not_latest)",
        },
    },
)
async def assign_update(
    body: AgentUpdateAssign,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentUpdateAssigned:
    assigned = await assign_agent_update(session, body)
    describe_action(
        request,
        action="update",
        changes={
            "update_channel": {"old": None, "new": assigned.channel},
            "agent_version": {"old": None, "new": assigned.version},
        },
    )
    return assigned
