"""Requests and responses of the panel incident API (plan.md §7, §10 «Инциденты»; ТЗ п. 19).

An incident is opened by the detection of T-40 for a line and a rule, or by a person from the
school card without a rule (ADR-007); the school and the provider always come from the line.
Status changes and comments add rows to ``incident_events`` and never rewrite them. Durations are
whole seconds, time is UTC, RFC 3339 (ADR-014). In a PATCH body an absent field stays unchanged
and ``null`` clears it.
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.schemas.pagination import Page
from app.schemas.statuses import IncidentMetric, IncidentStatus, LineStatus

# Entry of the incident history: creation, status change, comment, or ``restored_at`` set by
# the detection after M normal measurements in a row (ADR-007).
type IncidentEventKind = Literal["created", "status_change", "comment", "restored"]

DESCRIPTION_MAX_LENGTH = 2000
COMMENT_MAX_LENGTH = 2000


class IncidentBasisMetric(BaseModel):
    """Metric an incident is based on: the violating value next to its threshold (ТЗ п. 19).

    Units follow the metric name. Both values come from the measurement that triggered the rule
    and its ``thresholds_snapshot`` (ADR-004); a manual incident and ``no_connection`` have none.
    """

    metric: IncidentMetric
    value: float | None = Field(examples=[8.4], description="Фактическое значение")
    threshold: float | None = Field(
        examples=[20], description="Порог: минимум для download_mbps и upload_mbps, иначе максимум"
    )


class IncidentListItem(BaseModel):
    """Row of the incident list and card of the kanban (DESIGN.md §3.18)."""

    id: int
    number: str = Field(examples=["INC-2026-000123"], description="Уникальный номер инцидента")
    status: IncidentStatus
    school_id: int
    school_code: str = Field(description="School ID")
    school_name: str
    line_id: int
    line_status: LineStatus
    provider_id: int
    provider_name: str
    basis_metrics: list[IncidentBasisMetric]
    started_at: datetime = Field(
        description="Первое нарушение; у ручного инцидента — начало, указанное при создании"
    )
    duration_s: int | None = Field(
        ge=0, description="restored_at − started_at; null, пока показатели не восстановлены"
    )
    responsible_user_id: int | None
    responsible_user_name: str | None


class IncidentListItemPage(Page[IncidentListItem]):
    """Page of incidents, newest ``started_at`` first."""


class IncidentEventDetail(BaseModel):
    """Entry of the incident history (``incident_events``): who, when and what (ADR-007)."""

    id: int
    kind: IncidentEventKind
    from_status: IncidentStatus | None = Field(description="Только у status_change")
    to_status: IncidentStatus | None = Field(description="У status_change; у created — new")
    comment: str | None
    author_user_id: int | None = Field(
        description="null — действие системы: детекция T-40 или автозакрытие через 24 ч"
    )
    author_user_name: str | None
    created_at: datetime


class IncidentDetail(IncidentListItem):
    """Incident card (ТЗ п. 19, DESIGN.md §3.17): the list row plus timestamps and history."""

    rule_id: int | None = Field(description="Правило детекции; null — инцидент создан вручную")
    description: str | None = Field(description="Описание проблемы")
    last_violation_at: datetime | None = Field(
        description="Последнее нарушение по правилу; null у ручного инцидента"
    )
    sent_to_provider_at: datetime | None = Field(description="Перевод в sent_to_provider")
    restored_at: datetime | None = Field(
        description="Восстановление нормативных показателей; сброс при resolved → in_progress"
    )
    closed_at: datetime | None
    provider_reaction_s: int | None = Field(
        ge=0,
        description=(
            "restored_at − sent_to_provider_at; null без одной из отметок или если показатели "
            "восстановились до передачи поставщику"
        ),
    )
    created_at: datetime
    updated_at: datetime
    events: list[IncidentEventDetail] = Field(description="Вся история, по возрастанию created_at")


class IncidentCreate(BaseModel):
    """Manual incident from the school card: the fields of an automatic one without a rule.

    It starts as ``new``; the school and the provider come from the line (ADR-007).
    """

    line_id: int
    metrics: list[IncidentMetric] = Field(
        min_length=1,
        examples=[["download_mbps", "upload_mbps"]],
        description="Показатели-основания; значений и порогов у ручного инцидента нет",
    )
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    started_at: AwareDatetime | None = Field(
        default=None, description="Начало проблемы, не в будущем; по умолчанию — момент создания"
    )
    responsible_user_id: int | None = None

    @field_validator("metrics")
    @classmethod
    def check_unique(cls, value: list[IncidentMetric]) -> list[IncidentMetric]:
        if len(set(value)) != len(value):
            raise ValueError("показатели не должны повторяться")
        return value


class IncidentUpdate(BaseModel):
    """Changes of an incident by a person; the status changes only with its own endpoint."""

    responsible_user_id: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=DESCRIPTION_MAX_LENGTH)


class IncidentStatusChange(BaseModel):
    """Target status of an incident; a comment is required to close it (DESIGN.md §3.17)."""

    status: IncidentStatus
    comment: str | None = Field(default=None, min_length=1, max_length=COMMENT_MAX_LENGTH)

    @model_validator(mode="after")
    def check_comment(self) -> Self:
        if self.status == "closed" and self.comment is None:
            raise ValueError("для перевода в closed нужен комментарий")
        return self


class IncidentCommentCreate(BaseModel):
    """Comment of a person in the incident history (ТЗ п. 19)."""

    comment: str = Field(min_length=1, max_length=COMMENT_MAX_LENGTH)
