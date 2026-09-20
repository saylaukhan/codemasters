"""Requests and responses of the notification API of the panel (T-42; ТЗ п. 18; ADR-007).

A notification belongs to one user: the list, the counter and the stream always answer about the
caller, never about anyone else, so no endpoint takes a user id. Who gets a notification at all
is decided by the scope of ADR-008 when the incident moves. Time is UTC, RFC 3339 (ADR-014);
Russian strings of the panel come from ``web/src/lib/labels.ts`` by these codes (ADR-013).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.pagination import Page
from app.schemas.statuses import IncidentStatus

# What happened to the incident: it was opened by the detection (T-40), a person moved its
# status (T-41), or the measurements of the line came back to normal.
type NotificationKind = Literal["incident_opened", "incident_status_changed", "incident_restored"]

# Where a notification was delivered: the bell of the panel, Telegram, e-mail (ТЗ п. 18).
type NotificationChannel = Literal["panel", "telegram", "email"]

# Result of one delivery; ``skipped`` — the channel is not configured for that user.
type NotificationResult = Literal["sent", "failed", "skipped"]


class NotificationListItem(BaseModel):
    """Row of the notification panel (DESIGN.md §3.23)."""

    id: int
    kind: NotificationKind
    title: str = Field(examples=["Новый инцидент INC-2026-000123"])
    body: str = Field(examples=["Нет соединения · Школа №1, основная линия"])
    incident_id: int
    incident_number: str = Field(examples=["INC-2026-000123"])
    incident_status: IncidentStatus
    school_id: int
    school_name: str
    read_at: datetime | None = Field(description="null — не прочитано")
    created_at: datetime


class NotificationListItemPage(Page[NotificationListItem]):
    """Page of the notifications of the caller, newest first."""


class NotificationUnreadCount(BaseModel):
    """Counter on the bell of the header (DESIGN.md §3.5)."""

    unread: int = Field(ge=0, description="Непрочитанные уведомления пользователя")
