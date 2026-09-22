"""Rollout of the panel (T-69, docs/design/README.md §6.4): who is not connected, who is silent,
which agent versions are behind.

The numbers answer the same question as ``GET /api/dashboard/summary`` over the same schools —
«подключена» is a school with at least one active computer — so the share of a district here and
the counters of the main screen never disagree (T-22, T-60). Every window comes from the
settings (``offline_after_s``, ``rollout_silent_days``) and every «старая версия» from the
release table of T-50, never from a constant (ТЗ п. 11, п. 20; ADR-004).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.agent_releases import AgentChannel

# The four lists of docs/design/README.md §6.4; the key is the ``filter`` of the list endpoint.
type RolloutFilter = Literal["not_connected", "silent", "code_unused", "old_version"]


class RolloutListCounts(BaseModel):
    """How many schools each of the four lists holds, for the tabs of the screen (§6.4)."""

    not_connected: int = Field(ge=0, description="Нет ни одного активного компьютера")
    silent: int = Field(ge=0, description="Агент установлен, но молчит дольше rollout_silent_days")
    code_unused: int = Field(ge=0, description="Код установки выдан и не использован")
    old_version: int = Field(ge=0, description="Есть компьютер с версией ниже текущего релиза")


class RolloutCounts(BaseModel):
    """Progress of the rollout over a selection of schools: the oblast or one district."""

    schools_count: int = Field(
        ge=0, description="Активные школы выборки, как schools_count у GET /api/dashboard/summary"
    )
    schools_connected_count: int = Field(
        ge=0, description="Школы, у которых есть хотя бы один активный компьютер"
    )
    connected_pct: float = Field(
        ge=0, le=100, description="Доля подключённых школ; 0 при пустой выборке"
    )
    devices_count: int = Field(
        ge=0,
        description="Зарегистрированные компьютеры, кроме заблокированных, как devices_count "
        "у GET /api/dashboard/summary",
    )
    devices_alive_count: int = Field(
        ge=0, description="Компьютеры на связи: сигнал не старше offline_after_s"
    )
    devices_silent_count: int = Field(
        ge=0, description="Компьютеры, молчащие дольше rollout_silent_days"
    )
    devices_old_version_count: int = Field(
        ge=0, description="Компьютеры не на текущем релизе агента (T-50)"
    )


class RolloutRegionRow(RolloutCounts):
    """Row of «По районам и городам»: the same numbers for one district or city."""

    region_id: int
    region_name: str


class RolloutSummary(RolloutCounts):
    """Numbers of the rollout screen: the oblast, its districts and the four lists (§6.4)."""

    as_of: datetime = Field(description="Момент, на который собраны числа")
    schools_total_count: int = Field(
        ge=0, description="Школы тех же фильтров вместе с отключёнными: «350 из 366 в реестре»"
    )
    target_version: str | None = Field(
        description="Версия текущего активного stable-релиза агента; null — релизов нет (T-50)"
    )
    silent_days: int = Field(
        ge=1, description="Окно «молчит» из настроек: rollout_silent_days (ТЗ п. 20)"
    )
    alive_after_s: int = Field(
        ge=1, description="Окно «на связи» из настроек: offline_after_s (ADR-014)"
    )
    lists: RolloutListCounts
    regions: list[RolloutRegionRow] = Field(description="Районы и города выборки, по названию")


class RolloutSchoolItem(BaseModel):
    """School of one of the four lists, with the fact that put it there (§6.4)."""

    school_id: int
    school_code: str
    school_name: str
    region_id: int
    region_name: str
    devices_count: int = Field(ge=0, description="Активные компьютеры школы")
    devices_alive_count: int = Field(ge=0, description="Из них на связи")
    last_seen_at: datetime | None = Field(
        description="Последний сигнал любого компьютера школы; null — школу ни разу не слышали"
    )
    silent_days: int | None = Field(
        description="Сколько полных суток школа молчит; null — школа на связи или не подключена"
    )
    code_issued_at: datetime | None = Field(
        description="Когда выдан последний неиспользованный код установки (T-36)"
    )
    code_age_days: int | None = Field(
        description="Сколько полных суток коду: «не использован N дней»"
    )
    agent_versions: list[str] = Field(
        description="Версии агента компьютеров школы; версия ниже текущего релиза попадает "
        "в список «старая версия»"
    )
    has_contact: bool = Field(description="Есть ответственный за интернет (ТЗ п. 15)")


class RolloutSchoolPage(BaseModel):
    """Schools of one list, the worst first; ``total`` counts them before ``limit`` (§6.4)."""

    as_of: datetime
    filter: RolloutFilter
    target_version: str | None = Field(description="Текущий stable-релиз агента (T-50)")
    silent_days: int = Field(ge=1, description="Окно «молчит» из настроек")
    total: int = Field(ge=0, description="Сколько школ подходит критерию: подпись «Ещё N школ»")
    items: list[RolloutSchoolItem]


class AgentUpdateAssign(BaseModel):
    """«Назначить обновление»: which computers take ``version`` on their next configuration.

    Either ``device_ids`` or ``region_id`` — the chosen computers or every computer of a district;
    without both the whole scope of the user is meant.
    """

    version: str = Field(
        max_length=32,
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
        examples=["0.2.0"],
        description="Версия релиза T-50, которую должны поставить агенты",
    )
    device_ids: list[int] | None = Field(
        default=None, max_length=1000, description="Выбранные компьютеры; null — по району"
    )
    region_id: int | None = Field(
        default=None, description="Все компьютеры района или города; null — вся область видимости"
    )


class AgentUpdateAssigned(BaseModel):
    """What the assignment changed: the channel that delivers ``version`` and how many moved."""

    version: str
    channel: AgentChannel = Field(description="Канал обновления, который выдаёт эту версию (T-50)")
    devices_count: int = Field(ge=0, description="Компьютеры выборки")
    devices_changed_count: int = Field(
        ge=0, description="Из них переведены в канал; остальные уже получают эту версию"
    )
