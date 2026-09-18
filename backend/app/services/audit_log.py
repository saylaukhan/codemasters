"""Audit log of the administration (T-39, ТЗ п. 12, п. 16, п. 20; ADR-008): read-only list.

Records are written by the login and the audit middleware (``app/auth/audit.py``) and never
changed; here they are only filtered and paged, newest first. Only the Администратор reads the
log, his scope is the whole oblast, so RLS hides nothing here.
"""

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import cast

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.models import AuditLog
from app.schemas.audit import AuditAction, AuditEntityType, AuditLogListItem, AuditLogListItemPage
from app.services.references import page_of


def parsed_ip(q: str) -> IPv4Address | IPv6Address | None:
    try:
        return ip_address(q)
    except ValueError:
        return None


def search(q: str | None) -> list[ColumnElement[bool]]:
    """Filter of ``q``: a part of the e-mail, or the IP address as a whole."""
    if not q:
        return []
    by_email = AuditLog.user_email.ilike(f"%{q.strip()}%")
    ip = parsed_ip(q.strip())
    return [or_(by_email, AuditLog.ip == ip) if ip is not None else by_email]


def audit_item(row: AuditLog) -> AuditLogListItem:
    return AuditLogListItem(
        id=row.id,
        created_at=row.created_at,
        user_id=row.user_id,
        user_email=row.user_email,
        action=cast(AuditAction, row.action),
        entity_type=cast(AuditEntityType, row.entity_type),
        entity_id=row.entity_id,
        changes=row.changes,
        error_type=row.error_type,
        ip=row.ip,
    )


async def audit_list(
    session: AsyncSession,
    params: PageParams,
    *,
    period_from: datetime | None,
    period_to: datetime | None,
    user_id: int | None,
    actions: list[AuditAction] | None,
    entity_type: AuditEntityType | None,
    q: str | None,
) -> AuditLogListItemPage:
    filters = search(q)
    if period_from is not None:
        filters.append(AuditLog.created_at >= period_from)
    if period_to is not None:
        filters.append(AuditLog.created_at < period_to)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if actions:
        filters.append(AuditLog.action.in_(actions))
    if entity_type is not None:
        filters.append(AuditLog.entity_type == entity_type)
    query = (
        select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    rows, total = await page_of(session, query, params)
    return AuditLogListItemPage(
        items=[audit_item(row) for (row,) in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
