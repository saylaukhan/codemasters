"""Рассылки сводки для руководителя в админке (T-67, docs/design/README.md §6.2).

Одна рассылка — один охват: вся область или один район. День недели (1 — понедельник) и час
читаются в ``settings.timezone``, поэтому расписание задаётся здесь, а не в коде (ТЗ п. 11,
п. 20; ADR-004). В теле PATCH отсутствующее поле остаётся как было, ``null`` — 422.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.notifications import NotificationChannel, NotificationResult
from app.schemas.pagination import Page

# Охват рассылки: вся область или один район/город (строка ``regions``).
type DigestScope = Literal["oblast", "region"]

# 1 — понедельник … 7 — воскресенье, местное время Asia/Almaty (ADR-014).
type DigestWeekday = Annotated[
    int, Field(ge=1, le=7, description="1 — понедельник, 7 — воскресенье")
]
type DigestHour = Annotated[int, Field(ge=0, le=23, description="Час отправки в settings.timezone")]

# Адрес получателя: без проверки домена, но с обязательной «@» — контакт ответственного (ТЗ п. 15).
type DigestRecipients = Annotated[
    list[Annotated[str, Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")]],
    Field(
        max_length=100,
        description="Адреса рассылки; пустой список — сводка уходит только в Telegram",
    ),
]


class DigestSettingsCreate(BaseModel):
    """Новая рассылка сводки; охват «region» требует region_id, «oblast» — запрещает."""

    scope: DigestScope
    region_id: int | None = Field(default=None, description="Только и обязательно при scope=region")
    weekday: DigestWeekday
    hour: DigestHour
    recipients: DigestRecipients = []
    telegram_chat_id: str | None = Field(
        default=None, max_length=64, description="Чат Telegram; null — канал не используется"
    )
    is_active: bool = True

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if (self.region_id is not None) != (self.scope == "region"):
            raise ValueError("region_id указывается только и обязательно при scope=region")
        if not self.recipients and not self.telegram_chat_id:
            raise ValueError("укажите хотя бы один адрес или чат Telegram")
        return self


class DigestSettingsUpdate(BaseModel):
    """Изменения рассылки; охват и его цель не меняются."""

    weekday: DigestWeekday | SkipJsonSchema[None] = None
    hour: DigestHour | SkipJsonSchema[None] = None
    recipients: DigestRecipients | SkipJsonSchema[None] = None
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("weekday", "hour", "recipients", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class DigestSettingsDetail(BaseModel):
    """Рассылка сводки с наименованием района и временем последней отправки."""

    id: int
    scope: DigestScope
    region_id: int | None = Field(description="Только при scope=region")
    region_name: str | None
    weekday: DigestWeekday
    hour: DigestHour
    recipients: DigestRecipients
    telegram_chat_id: str | None
    is_active: bool = Field(description="Отключённая рассылка не уходит по расписанию")
    last_sent_at: datetime | None = Field(description="null — сводка ещё не уходила")


class DigestSettingsDetailPage(Page[DigestSettingsDetail]):
    """Страница рассылок сводки."""


class DigestDelivery(BaseModel):
    """Одна попытка доставки сводки: канал, адресат и что из этого вышло (ТЗ п. 18)."""

    channel: NotificationChannel
    result: NotificationResult = Field(description="skipped — канал не настроен на сервере")
    target: str | None
    error: str | None = Field(description="Причина skipped или failed; null у доставленной")


class DigestSendResult(BaseModel):
    """Итог «Отправить сейчас»: каждая попытка записана в notification_log (ТЗ п. 18)."""

    sent_at: datetime
    deliveries: list[DigestDelivery]
