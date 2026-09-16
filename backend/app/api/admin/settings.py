"""System settings of the admin panel (T-37; plan.md §10 has no path for them): read, change.

Contract stubs: every endpoint answers 501 until T-37. The settings are a single record, so the
path has no id and there is neither POST nor DELETE.
"""

from fastapi import APIRouter, Security

from app.core.deps import user_token
from app.core.errors import not_implemented
from app.schemas.settings import SettingsDetail, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["admin"], dependencies=[Security(user_token)])


@router.get(
    "",
    summary="Системные настройки: сервер замеров, интервалы агента, правила расчётов",
)
async def get_system_settings() -> SettingsDetail:
    raise not_implemented("T-37")


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
async def update_system_settings(body: SettingsUpdate) -> SettingsDetail:
    raise not_implemented("T-37")
