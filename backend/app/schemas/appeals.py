"""Requests and responses of appeals to providers (plan.md §8, §10 «Обращения»; ТЗ п. 17).

A draft is not stored and has no number: the number is assigned by «Отправить» (ADR-011).
The context the server builds holds no personal data; contacts of the school are put into the
text only after generation (ADR-011). An appeal has the six statuses of an incident, each
change is an ``appeal_events`` row (ADR-007, ADR-011).
"""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.analytics import MetricStats
from app.schemas.pagination import Page
from app.schemas.statuses import IncidentStatus
from app.schemas.thresholds import ThresholdValues

# E-mail to the provider: not_sent — SMTP is not configured, the provider has no address or
# sending failed; the PDF is stored either way (ADR-011).
type AppealDeliveryStatus = Literal["sent", "not_sent"]


class AppealDraftRequest(BaseModel):
    """What the appeal is about and the problem period.

    Exactly one target: ``incident_id``, or ``school_id`` together with ``line_id``.
    """

    incident_id: int | None = Field(
        default=None, description="Из карточки инцидента: школа и линия — из инцидента"
    )
    school_id: int | None = Field(default=None, description="Из карточки школы, вместе с line_id")
    line_id: int | None = Field(
        default=None, description="Линия школы: обращение уходит её поставщику"
    )
    period_from: AwareDatetime = Field(
        description="Начало периода, включительно; для инцидента — его started_at"
    )
    period_to: AwareDatetime = Field(
        description="Конец периода, не включая; для инцидента — restored_at или текущий момент"
    )

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if self.incident_id is not None:
            valid = self.school_id is None and self.line_id is None
        else:
            valid = self.school_id is not None and self.line_id is not None
        if not valid:
            raise ValueError("укажите incident_id либо school_id и line_id")
        if self.period_to <= self.period_from:
            raise ValueError("period_to должен быть позже period_from")
        return self


class AppealContext(BaseModel):
    """Facts of an appeal built by the server (ТЗ п. 17, plan.md §8); no personal data.

    Metrics cover Ethernet measurements of the line in the period, without Wi-Fi (ADR-012).
    """

    incident_id: int | None
    incident_number: str | None = Field(examples=["INC-2026-000123"])
    school_id: int
    school_code: str = Field(description="School ID")
    school_name: str
    line_id: int
    line_identifier: str | None = Field(description="Идентификатор линии у поставщика")
    provider_id: int
    provider_name: str
    contract_number: str | None
    contract_date: date | None
    contract_down_mbps: float | None
    contract_up_mbps: float | None
    period_from: datetime = Field(description="Начало периода, включительно")
    period_to: datetime = Field(description="Конец периода, не включительно")
    measurements_count: int = Field(ge=0)
    problem_count: int = Field(ge=0, description="Замеры unstable, critical или offline")
    download_mbps: MetricStats | None = Field(description="null — замеров со значением нет")
    upload_mbps: MetricStats | None
    ping_ms: MetricStats | None
    jitter_ms: MetricStats | None
    packet_loss_pct: MetricStats | None
    thresholds: ThresholdValues = Field(
        description="Пороги оценки: thresholds_snapshot последнего замера периода; без замеров — "
        "действующий профиль линии (ADR-004)"
    )
    outages_count: int = Field(ge=0)
    outages_duration_s: int = Field(
        ge=0, description="Простои линии за период: outages и пропуски heartbeat (ADR-014)"
    )


class AppealDraft(BaseModel):
    """Editable draft of an appeal; nothing is stored (ТЗ п. 17, T-47)."""

    subject: str
    text: str = Field(
        description="Текст письма в Markdown (абзацы, жирный, списки); контакты ответственного "
        "подставлены после генерации (ADR-011)"
    )
    ai_generated: bool = Field(
        description="false — модель недоступна или не настроена: subject и text — пустой шаблон"
    )
    recipient_email: str | None = Field(
        description="appeals_email поставщика; пусто — адрес не задан, письмо не уйдёт"
    )
    context: AppealContext


class AppealCreate(AppealDraftRequest):
    """«Отправить»: references and period of the draft with the text edited by the user."""

    subject: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=20000, description="Текст письма в Markdown")
    user_comment: str | None = Field(
        default=None,
        max_length=2000,
        description="Комментарий пользователя: в обращении — отдельно от текста (ТЗ п. 17)",
    )


class AppealUpdate(BaseModel):
    """Status change or comment by the provider or a user; at least one of them."""

    status: IncidentStatus | SkipJsonSchema[None] = None
    comment: str | None = Field(
        default=None, min_length=1, max_length=2000, description="Комментарий в историю"
    )

    @field_validator("status", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value

    @model_validator(mode="after")
    def check_change(self) -> Self:
        if self.status is None and self.comment is None:
            raise ValueError("укажите status или comment")
        return self


class AppealListItem(BaseModel):
    """Row of the appeal list and of the provider cabinet (ТЗ п. 17, T-44)."""

    id: int
    number: str = Field(examples=["ОБР-2026-000045"])
    status: IncidentStatus
    subject: str
    incident_id: int | None
    incident_number: str | None = Field(examples=["INC-2026-000123"])
    school_id: int
    school_code: str = Field(description="School ID")
    school_name: str
    line_id: int
    provider_id: int
    provider_name: str
    sent_at: datetime
    delivery_status: AppealDeliveryStatus


class AppealListItemPage(Page[AppealListItem]):
    """Page of appeals, newest ``sent_at`` first."""


class AppealEventDetail(BaseModel):
    """Entry of the appeal history: sending, status change or comment (ТЗ п. 17)."""

    id: int
    created_at: datetime
    author_user_id: int
    author_user_name: str
    status: IncidentStatus | None = Field(description="Новый статус; null — только комментарий")
    comment: str | None


class AppealDetail(BaseModel):
    """Sent appeal: number, text, context at sending, e-mail delivery and history."""

    id: int
    number: str = Field(examples=["ОБР-2026-000045"], description="Присвоен при отправке")
    status: IncidentStatus
    subject: str
    text: str = Field(description="Текст письма в Markdown")
    user_comment: str | None
    context: AppealContext
    sent_at: datetime
    recipient_email: str | None = Field(description="appeals_email поставщика при отправке")
    delivery_status: AppealDeliveryStatus = Field(
        description="not_sent — письмо не ушло (SMTP не настроен, нет адреса, ошибка); PDF сохранён"
    )
    events: list[AppealEventDetail] = Field(
        description="История, по возрастанию created_at; первая запись — отправка"
    )
