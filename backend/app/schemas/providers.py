"""Score of a provider and the claim act (T-68; ТЗ п. 14, п. 19; docs/design/README.md §6.3).

The numbers of a row come from the aggregates of T-19 through the analytics of T-27 and from
the incidents of T-45, so they are the same numbers the analytics screen shows for the same
period: measurements of the main lines without Wi-Fi (ADR-003), availability in working hours
(T-16, ADR-014), incidents by ``started_at`` (ADR-007). The score itself is 100 minus the
penalty of every part, each part weighted by a setting, and a score below
``pass_pct`` is «ниже нормы» — neither the weights nor that threshold is a constant of the code
(ТЗ п. 11, п. 20; ADR-004). Percentages are 0–100, datetimes are UTC RFC 3339.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.statuses import SchoolStatus

# Verdict on the score: at or above the passing threshold of the settings, or below it.
type ProviderScoreVerdict = Literal["pass", "below_norm"]


class ProviderScoreWeights(BaseModel):
    """Weights of the parts and the passing threshold, as the admin panel holds them (T-37)."""

    below_contract: float = Field(ge=0, le=100, description="Вес доли замеров ниже договора")
    availability: float = Field(ge=0, le=100, description="Вес нехватки доступности")
    reaction: float = Field(ge=0, le=100, description="Вес просрочки реакции на инцидент")
    incidents: float = Field(ge=0, le=100, description="Вес числа инцидентов на школу")
    pass_pct: float = Field(ge=0, le=100, description="Оценка ниже этой — «ниже нормы»")
    reaction_norm_hours: float = Field(gt=0, description="Норма реакции на инцидент, ч")


class ProviderScoreRow(BaseModel):
    """One provider over the period: what is counted and the score it adds up to."""

    id: int
    name: str
    schools_count: int = Field(ge=0, description="Школ на основных линиях поставщика")
    lines_count: int = Field(ge=0)
    measurements_count: int = Field(ge=0)
    problem_count: int = Field(ge=0)
    problem_pct: float | None = Field(ge=0, le=100, description="Доля проблемных замеров, %")
    availability_pct: float | None = Field(
        ge=0, le=100, description="Доступность школ поставщика в рабочие часы (T-16, ADR-014)"
    )
    below_contract_pct: float | None = Field(
        ge=0,
        le=100,
        description="Доля замеров ниже договорной скорости, %; null без договорных значений",
    )
    incidents_opened: int = Field(ge=0, description="Инцидентов начато за период (по started_at)")
    incidents_closed: int = Field(ge=0, description="Из них с восстановлением линии (restored_at)")
    reaction_median_s: int | None = Field(
        ge=0,
        description="Медиана времени до первой смены статуса инцидента, с; null без таких",
    )
    reaction_worst_s: int | None = Field(ge=0, description="Худшее время до смены статуса, с")
    restore_avg_s: int | None = Field(
        ge=0, description="Среднее устранение: restored_at − started_at, с (T-45)"
    )
    restore_worst_s: int | None = Field(ge=0, description="Худшее устранение, с")
    lines_below_norm_count: int = Field(
        ge=0,
        description="Линий, у которых договорная скорость ниже порога профиля — «не претензия»",
    )
    score: float | None = Field(
        ge=0, le=100, description="Оценка 0–100; null — за период нет ни одного замера"
    )
    verdict: ProviderScoreVerdict | None = Field(
        description="below_norm — оценка ниже порога настроек; null вместе с пустой оценкой"
    )


class ProviderScoreReport(BaseModel):
    """Rows of every provider the user may see, ordered by name (ADR-008)."""

    period_from: datetime
    period_to: datetime
    weights: ProviderScoreWeights
    availability_min_pct: float = Field(ge=0, le=100, description="Порог доступности (п. 11)")
    rows: list[ProviderScoreRow]


class ProviderSchoolRow(BaseModel):
    """School on a main line of the provider: its status now and its numbers of the period."""

    school_id: int
    name: str
    region_name: str | None
    status: SchoolStatus = Field(description="Статус школы сейчас (ADR-004)")
    measurements_count: int = Field(ge=0)
    below_contract_pct: float | None = Field(ge=0, le=100)
    availability_pct: float | None = Field(ge=0, le=100)
    sustained_mismatch: bool | None = Field(
        description="Устойчиво ниже договора по пересчёту T-29; null — ещё не рассчитано"
    )


class ProviderLineBelowNorm(BaseModel):
    """Line whose contract itself is below the thresholds it is judged by — «не претензия».

    Nothing here is the fault of the provider: the contract promises less than ТЗ п. 11 asks,
    so the school needs a new contract, not an appeal (docs/design/README.md §6.3).
    """

    line_id: int
    school_id: int
    school_name: str
    region_name: str | None
    contract_down_mbps: float | None
    contract_up_mbps: float | None
    download_min_mbps: float = Field(ge=0, description="Порог профиля, применимого к линии")
    upload_min_mbps: float = Field(ge=0)


class ProviderScoreDetail(BaseModel):
    """Card of one provider: its row, its schools and the lines whose contract is below the norm."""

    period_from: datetime
    period_to: datetime
    weights: ProviderScoreWeights
    availability_min_pct: float = Field(ge=0, le=100)
    provider: ProviderScoreRow
    appeals_email: str | None = Field(description="Адрес поставщика для обращений и акта (T-48)")
    schools: list[ProviderSchoolRow]
    lines_below_norm: list[ProviderLineBelowNorm]
