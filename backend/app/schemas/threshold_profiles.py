"""Requests and responses of threshold profiles in the admin panel (plan.md §10 «Админка», T-37).

A measurement is evaluated by the most specific active profile: its line, then its district, then
the global one (ADR-004). Each measurement keeps its own snapshot, so a change never touches
history. The global profile comes from T-17 and cannot be switched off; a profile is never
deleted, ``is_active = false`` switches it off. In a PATCH body an absent field stays unchanged
and ``null`` is a 422.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.pagination import Page
from app.schemas.statuses import LineStatus
from app.schemas.thresholds import ThresholdValues

# Target of a profile: the whole oblast, a district or city (a row of ``regions``), one line.
type ThresholdProfileScope = Literal["global", "district", "line"]

UNSTABLE_DEVIATION = (
    "Наибольшее отклонение одного показателя от порога, % от порога, при котором замер — "
    "unstable; больше или нарушено несколько показателей — critical (ADR-004)"
)


class ThresholdProfileCreate(BaseModel):
    """New profile of a district or a line; it is active from the next measurement."""

    scope: ThresholdProfileScope
    region_id: int | None = Field(
        default=None, description="Только и обязательно при scope=district"
    )
    line_id: int | None = Field(default=None, description="Только и обязательно при scope=line")
    thresholds: ThresholdValues
    unstable_deviation_pct: float = Field(
        ge=0, le=100, examples=[30], description=UNSTABLE_DEVIATION
    )

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if (self.region_id is not None) != (self.scope == "district"):
            raise ValueError("region_id указывается только и обязательно при scope=district")
        if (self.line_id is not None) != (self.scope == "line"):
            raise ValueError("line_id указывается только и обязательно при scope=line")
        return self


class ThresholdProfileUpdate(BaseModel):
    """Changes of a profile; its scope and target never change."""

    thresholds: ThresholdValues | SkipJsonSchema[None] = None
    unstable_deviation_pct: Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None] = None
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("thresholds", "unstable_deviation_pct", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class ThresholdProfileDetail(BaseModel):
    """Threshold profile with the names of its target."""

    id: int
    scope: ThresholdProfileScope
    region_id: int | None = Field(description="Только при scope=district")
    region_name: str | None
    line_id: int | None = Field(description="Только при scope=line")
    school_id: int | None = Field(description="Школа линии; только при scope=line")
    school_name: str | None
    provider_name: str | None = Field(description="Поставщик линии; только при scope=line")
    line_status: LineStatus | None = Field(description="Только при scope=line")
    thresholds: ThresholdValues
    unstable_deviation_pct: float = Field(
        ge=0, le=100, examples=[30], description=UNSTABLE_DEVIATION
    )
    is_active: bool = Field(
        description="Отключённый профиль не применяется: действует следующий по цепочке"
    )


class ThresholdProfileDetailPage(Page[ThresholdProfileDetail]):
    """Page of threshold profiles."""
