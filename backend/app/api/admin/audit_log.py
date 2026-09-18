"""Audit log (plan.md §10 «Админка»): sign-ins, administrative actions, transfer errors.

Only the Администратор reads the log (ADR-008, T-39). The log is read-only: records are
written by the login and the audit middleware (T-20) and never changed or deleted.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.audit import AuditAction, AuditEntityType, AuditLogListItemPage
from app.services.audit_log import audit_list

router = APIRouter(
    prefix="/audit-log", tags=["admin"], dependencies=[Depends(require("audit:read"))]
)


@router.get("", summary="Журнал аудита, новые сверху")
async def list_audit_log(
    params: Annotated[PageParams, Depends(page_params)],
    period_from: Annotated[
        AwareDatetime | None, Query(description="Начало периода по created_at, включительно")
    ] = None,
    period_to: Annotated[
        AwareDatetime | None, Query(description="Конец периода по created_at, не включается")
    ] = None,
    user_id: int | None = None,
    action: Annotated[
        list[AuditAction] | None, Query(description="Действия; несколько — повтором параметра")
    ] = None,
    entity_type: Annotated[AuditEntityType | None, Query()] = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=255, description="Часть e-mail пользователя или IP-адрес"),
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuditLogListItemPage:
    return await audit_list(
        session,
        params,
        period_from=period_from,
        period_to=period_to,
        user_id=user_id,
        actions=action,
        entity_type=entity_type,
        q=q,
    )
