"""Requests and responses of the incident rule admin API (ТЗ п. 18, п. 20; plan.md §7; ADR-007).

A rule opens an incident on a line after N violations in a row or after T minutes of violation,
whichever comes first, and sets ``restored_at`` after M normal results in a row (T-40).
A violation is a line measurement without Wi‑Fi whose metric is worse than the threshold in its
``thresholds_snapshot`` (ADR-004, ADR-012): speeds below the minimum, ping, jitter and loss above
the maximum; ``no_connection`` is an offline measurement or a missing heartbeat in working hours
(ADR-014). Rules apply to every line; a rule is switched off with ``is_active``, never deleted,
since incidents refer to it. Defaults of ADR-007 (3, 30 min, 2) are examples only.
In a PATCH body an absent field stays unchanged, ``null`` clears a nullable field, and ``null``
for any other field is a 422.
"""

from typing import Annotated, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.pagination import Page
from app.schemas.statuses import IncidentMetric

NO_CONDITION = "задайте consecutive_violations или duration_min"


class IncidentRuleCreate(BaseModel):
    """New rule: at least one opening condition, N in a row or T minutes."""

    name: str = Field(min_length=1, max_length=255, examples=["Download ниже порога"])
    metric: IncidentMetric
    consecutive_violations: int | None = Field(
        default=None, ge=1, examples=[3], description="N нарушений подряд для инцидента"
    )
    duration_min: int | None = Field(
        default=None, ge=1, examples=[30], description="Длительность нарушения для инцидента, мин"
    )
    recovery_normal_count: int = Field(
        ge=1, examples=[2], description="M нормальных подряд для восстановления (restored_at)"
    )

    @model_validator(mode="after")
    def check_condition(self) -> Self:
        if self.consecutive_violations is None and self.duration_min is None:
            raise ValueError(NO_CONDITION)
        return self


class IncidentRuleUpdate(BaseModel):
    """Changes of a rule; ``metric`` is fixed: another metric is a new rule."""

    name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None
    consecutive_violations: int | None = Field(default=None, ge=1)
    duration_min: int | None = Field(default=None, ge=1)
    recovery_normal_count: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("name", "recovery_normal_count", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value

    @model_validator(mode="after")
    def check_condition(self) -> Self:
        cleared = {"consecutive_violations", "duration_min"} <= self.model_fields_set
        if cleared and self.consecutive_violations is None and self.duration_min is None:
            raise ValueError(NO_CONDITION)
        return self


class IncidentRuleDetail(BaseModel):
    """Incident rule as the detection of T-40 applies it."""

    id: int
    name: str
    metric: IncidentMetric
    consecutive_violations: int | None = Field(description="N нарушений подряд для инцидента")
    duration_min: int | None = Field(description="Длительность нарушения для инцидента, мин")
    recovery_normal_count: int = Field(
        description="M нормальных подряд для восстановления (restored_at)"
    )
    is_active: bool = Field(description="false — правило не применяется, его инциденты остаются")


class IncidentRuleDetailPage(Page[IncidentRuleDetail]):
    """Page of the incident rules."""
