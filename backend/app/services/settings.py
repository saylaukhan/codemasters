"""The single row of ``settings``: system-wide values every service reads (T-05, T-16, T-17).

Nothing here has a default in code (``app/schemas/settings.py``): the values come from the
migration that added the column and from ``make seed``, and the admin panel changes them
(ТЗ п. 20, T-37). A database without that row is an incomplete installation, so a request that
needs it answers 503, not 500.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import SystemSettings

SETTINGS_ID = 1
NOT_CONFIGURED = "not_configured"
NOT_CONFIGURED_DETAIL = (
    "Система не настроена: нет системных настроек, расписания или профиля порогов — "
    "примените миграции и выполните make seed"
)


async def system_settings(session: AsyncSession) -> SystemSettings:
    """System settings; 503 while ``make seed`` has not created the row."""
    settings = await session.get(SystemSettings, SETTINGS_ID)
    if settings is None:
        raise ApiError(503, NOT_CONFIGURED, NOT_CONFIGURED_DETAIL)
    return settings
