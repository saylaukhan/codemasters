"""Requests and responses of measurement schedules in the admin panel (plan.md §10 «Админка», T-37).

An agent measures in the slots of the most specific active schedule of its school: the school,
then its district, then the global one; it gets them from ``GET /api/agent/config`` (T-17) and
picks a random moment inside each slot (ТЗ п. 2, plan.md §4.2). Slot times are local Asia/Almaty
times without an offset (ADR-014). The global schedule comes from ``make seed`` and cannot be
switched off; a schedule is never deleted. In a PATCH body an absent field stays unchanged and
``null`` is a 422.
"""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.agent import ScheduleSlot
from app.schemas.pagination import Page

# Target of a schedule: the whole oblast, a district or city (a row of ``regions``), one school.
type ScheduleScope = Literal["global", "district", "school"]


def check_slots(slots: list[ScheduleSlot]) -> list[ScheduleSlot]:
    """Slots are local times, each ends after it starts, none overlap; returned by start."""
    for slot in slots:
        if slot.start.tzinfo is not None or slot.end.tzinfo is not None:
            raise ValueError("start и end слотов указываются без пояса")
        if slot.end <= slot.start:
            raise ValueError("end слота должен быть позже start")
    ordered = sorted(slots, key=lambda slot: slot.start)
    for previous, current in pairwise(ordered):
        if current.start < previous.end:
            raise ValueError("слоты не должны пересекаться")
    return ordered


# 3–5 measurements a day (ТЗ п. 2); the example is the default of «Решения по умолчанию».
ScheduleSlots = Annotated[
    list[ScheduleSlot],
    Field(
        min_length=3,
        max_length=5,
        examples=[
            [
                {"start": "08:30:00", "end": "09:00:00"},
                {"start": "11:00:00", "end": "11:30:00"},
                {"start": "13:30:00", "end": "14:00:00"},
                {"start": "16:00:00", "end": "16:30:00"},
            ]
        ],
        description="3–5 непересекающихся слотов, местное время Asia/Almaty; хранятся по start",
    ),
    AfterValidator(check_slots),
]


class ScheduleCreate(BaseModel):
    """New schedule of a district or a school; agents get it with the next configuration."""

    scope: ScheduleScope
    region_id: int | None = Field(
        default=None, description="Только и обязательно при scope=district"
    )
    school_id: int | None = Field(default=None, description="Только и обязательно при scope=school")
    slots: ScheduleSlots

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if (self.region_id is not None) != (self.scope == "district"):
            raise ValueError("region_id указывается только и обязательно при scope=district")
        if (self.school_id is not None) != (self.scope == "school"):
            raise ValueError("school_id указывается только и обязательно при scope=school")
        return self


class ScheduleUpdate(BaseModel):
    """Changes of a schedule; its scope and target never change, slots are replaced as a whole."""

    slots: ScheduleSlots | SkipJsonSchema[None] = None
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("slots", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class ScheduleDetail(BaseModel):
    """Measurement schedule with the names of its target."""

    id: int
    scope: ScheduleScope
    region_id: int | None = Field(description="Только при scope=district")
    region_name: str | None
    school_id: int | None = Field(description="Только при scope=school")
    school_name: str | None
    slots: ScheduleSlots
    is_active: bool = Field(
        description="Отключённое расписание не применяется: действует следующее по цепочке"
    )


class ScheduleDetailPage(Page[ScheduleDetail]):
    """Page of measurement schedules."""
