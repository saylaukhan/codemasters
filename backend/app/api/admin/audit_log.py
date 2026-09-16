"""Audit log (plan.md §10 «Админка»): sign-ins, administrative actions, transfer errors.

Contract stub: answers 501 until T-39. Only the Администратор reads the log (ADR-008, T-39).
The log is read-only: records are written by the audit middleware (T-20) and never deleted.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from pydantic import AwareDatetime

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.audit import AuditAction, AuditEntityType, AuditLogListItemPage

router = APIRouter(prefix="/audit-log", tags=["admin"], dependencies=[Security(user_token)])


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
) -> AuditLogListItemPage:
    raise not_implemented("T-39")
