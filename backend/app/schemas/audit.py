"""Response of the audit log (plan.md §9, §10 «Админка»; ТЗ п. 12, п. 16, п. 20).

The audit middleware (T-20) writes sign-ins, changing actions of the panel and rejected agent
requests; records are never changed or deleted, also for blocked users (ADR-008). Passwords,
tokens and installation codes never get into the log.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, IPvAnyAddress

from app.schemas.pagination import Page

# What happened: sign-ins and transfer errors (ТЗ п. 12), administrative actions and blocking
# (ТЗ п. 16); status_change — incidents and appeals, transfer_error — rejected agent request (T-39),
# import — a registry of contracts loaded into the lines (T-61).
type AuditAction = Literal[
    "login_success",
    "login_failure",
    "create",
    "update",
    "block",
    "unblock",
    "password_reset",
    "status_change",
    "export",
    "import",
    "transfer_error",
]

# Kind of record the action touched, after the tables of plan.md §5.
type AuditEntityType = Literal[
    "user",
    "school",
    "line",
    "monitoring_point",
    "school_contact",
    "device",
    "enrollment_code",
    "region",
    "provider",
    "connection_type",
    "threshold_profile",
    "schedule",
    "setting",
    "incident_rule",
    "agent_release",
    "incident",
    "appeal",
    "appeal_template",
    "export",
]


class AuditLogListItem(BaseModel):
    """One audit record: who, when, what (T-39)."""

    id: int
    created_at: datetime = Field(description="Момент действия")
    user_id: int | None = Field(description="Пусто — запрос агента или вход с неизвестным e-mail")
    user_email: str | None = Field(
        description="E-mail пользователя на момент действия; при login_failure — введённый"
    )
    action: AuditAction
    entity_type: AuditEntityType = Field(
        description="login_* — user, transfer_error — device, export — export"
    )
    entity_id: int | None = Field(
        description="Пусто, если запись не определена: неизвестный e-mail или токен устройства"
    )
    changes: dict[str, Any] | None = Field(
        examples=[{"is_active": {"old": True, "new": False}}],
        description="Изменённые поля {поле: {old, new}}; пароли, токены и коды не пишутся",
    )
    error_type: str | None = Field(
        examples=["invalid_credentials"],
        description="type ошибки problem+json для login_failure и transfer_error",
    )
    ip: IPvAnyAddress | None = Field(description="IP-адрес клиента")


class AuditLogListItemPage(Page[AuditLogListItem]):
    """Page of the audit log, newest first."""
