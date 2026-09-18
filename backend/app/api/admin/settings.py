"""System settings of the admin panel (T-37; plan.md §10 has no path for them): read, change.

The settings are a single record, so the path has no id and there is neither POST nor DELETE.
Every change goes to the audit log with the changed fields (T-37).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.schemas.settings import SettingsDetail, SettingsUpdate
from app.services import config_admin

router = APIRouter(
    prefix="/settings", tags=["admin"], dependencies=[Depends(require("settings:manage"))]
)


@router.get(
    "",
    summary="Системные настройки: сервер замеров, интервалы агента, правила расчётов",
)
async def get_system_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsDetail:
    return await config_admin.settings_detail(session)


@router.patch(
    "",
    summary="Изменить системные настройки",
    description=(
        "Объекты speedtest и default_working_hours заменяются целиком: speedtest без ndt7_url "
        "отключает резервный сервер. Агенты получают новые значения со следующей конфигурацией: "
        "новый ETag в GET /api/agent/config (T-17). offline_after_s не больше "
        "heartbeat_interval_s с учётом сохранённых значений — 422."
    ),
)
async def update_system_settings(
    body: SettingsUpdate, request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> SettingsDetail:
    settings, changes = await config_admin.update_settings(session, body)
    describe_action(request, changes=changes or None)
    return settings
