"""System settings of the admin panel: the single row of ``settings`` (ТЗ п. 11, п. 20; T-37).

Nothing here has a default in code: ``make seed`` stores the values of «Решения по умолчанию»,
which are only the examples below, and the admin panel changes them. Agents get their part from
``GET /api/agent/config`` (T-17). In a PATCH body an absent field stays unchanged, ``null`` is
a 422, and an object (``speedtest``, ``default_working_hours``) is replaced as a whole.
"""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.agent import SpeedtestServers
from app.schemas.schools import WorkingHours

# Contact of the administrator on the sign-in screen: an e-mail and a telephone fit (T-65).
SUPPORT_CONTACT_MAX_LENGTH = 255


class SettingsDetail(BaseModel):
    """System-wide values used by the agent configuration, statuses, reports and exports."""

    speedtest: SpeedtestServers = Field(
        description="Сервер замеров: LibreSpeed и резервный ndt7 (ADR-012)"
    )
    heartbeat_interval_s: int = Field(ge=1, examples=[300])
    config_refresh_interval_s: int = Field(ge=1, examples=[900])
    offline_after_s: int = Field(
        ge=1,
        examples=[900],
        description="Нет heartbeat дольше — offline в рабочие часы, no_data вне их (ADR-014)",
    )
    school_status_measurements_count: int = Field(
        ge=1,
        examples=[3],
        description="Сколько последних замеров основной линии дают статус школы (ADR-004)",
    )
    default_working_hours: WorkingHours = Field(
        description="С ними создаётся школа; рабочие часы существующих школ не меняются (ADR-014)"
    )
    availability_min_pct: float = Field(
        ge=0, le=100, examples=[99], description="Порог доступности за период (п. 11)"
    )
    contract_mismatch_threshold_pct: float = Field(
        ge=0,
        le=100,
        examples=[50],
        description="Устойчивое несоответствие: доля замеров основной линии ниже договора за "
        "окно больше этой (п. 14, T-29)",
    )
    contract_mismatch_window_days: int = Field(ge=1, examples=[7])
    enrollment_code_ttl_days: int = Field(
        ge=1, examples=[7], description="Срок действия кода установки агента (ADR-005)"
    )
    export_sync_max_rows: int = Field(
        ge=1,
        examples=[10000],
        description="Выгрузка больше стольких строк и любой PDF формируются в фоне (T-33)",
    )
    export_retention_days: int = Field(
        ge=1, examples=[7], description="Срок хранения файла выгрузки (T-33)"
    )
    incident_auto_close_hours: int = Field(
        ge=1,
        examples=[24],
        description="Инцидент в resolved переходит в closed через столько часов (ADR-007)",
    )
    agent_queue_retention_days: int = Field(
        ge=1,
        le=365,
        examples=[30],
        description="Сколько суток агент хранит замер в очереди и насколько старый замер "
        "принимает сервер (ADR-006)",
    )
    attention_incident_unassigned_hours: int = Field(
        ge=1,
        examples=[24],
        description="Инцидент без ответственного дольше стольких часов попадает в «Требуют "
        "внимания» главного экрана (T-60)",
    )
    attention_appeal_no_answer_hours: int = Field(
        ge=1,
        examples=[48],
        description="Обращение «Передан поставщику» без движения дольше стольких часов "
        "считается оставшимся без ответа (T-60)",
    )
    rollout_silent_days: int = Field(
        ge=1,
        examples=[7],
        description="Установленный агент без heartbeat дольше стольких суток — школа «молчит» "
        "в разделе «Внедрение» (T-69)",
    )
    password_reset_ttl_minutes: int = Field(
        ge=1,
        examples=[30],
        description="Срок действия ссылки «Забыли пароль?» в минутах (T-65)",
    )
    support_contact: str = Field(
        max_length=SUPPORT_CONTACT_MAX_LENGTH,
        examples=["admin@edu.vko.kz, +7 7232 00-00-00"],
        description="Контакт администратора на экране входа, когда SMTP не настроен; "
        "пусто — контакт не показывается (T-65)",
    )
    provider_score_weight_below_contract: float = Field(
        ge=0,
        le=100,
        examples=[40],
        description="Вес доли замеров ниже договора в оценке поставщика (T-68, §6.3)",
    )
    provider_score_weight_availability: float = Field(
        ge=0, le=100, examples=[20], description="Вес нехватки доступности в оценке поставщика"
    )
    provider_score_weight_reaction: float = Field(
        ge=0, le=100, examples=[25], description="Вес просрочки реакции на инцидент в оценке"
    )
    provider_score_weight_incidents: float = Field(
        ge=0, le=100, examples=[15], description="Вес числа инцидентов на школу в оценке"
    )
    provider_score_pass_pct: float = Field(
        ge=0, le=100, examples=[70], description="Оценка ниже этой — «ниже нормы» (§6.3)"
    )
    provider_score_reaction_norm_hours: float = Field(
        gt=0,
        examples=[4],
        description="Норма реакции на инцидент, ч: медиана вдвое больше нормы — полный штраф",
    )


class SettingsUpdate(BaseModel):
    """Changes of the settings; every column is NOT NULL."""

    speedtest: SpeedtestServers | SkipJsonSchema[None] = None
    heartbeat_interval_s: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    config_refresh_interval_s: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    offline_after_s: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    school_status_measurements_count: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    default_working_hours: WorkingHours | SkipJsonSchema[None] = None
    availability_min_pct: Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None] = None
    contract_mismatch_threshold_pct: (
        Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None]
    ) = None
    contract_mismatch_window_days: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    enrollment_code_ttl_days: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    export_sync_max_rows: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    export_retention_days: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    incident_auto_close_hours: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    agent_queue_retention_days: Annotated[int, Field(ge=1, le=365)] | SkipJsonSchema[None] = None
    attention_incident_unassigned_hours: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    attention_appeal_no_answer_hours: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    rollout_silent_days: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    password_reset_ttl_minutes: Annotated[int, Field(ge=1)] | SkipJsonSchema[None] = None
    support_contact: (
        Annotated[str, Field(max_length=SUPPORT_CONTACT_MAX_LENGTH)] | SkipJsonSchema[None]
    ) = None
    provider_score_weight_below_contract: (
        Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None]
    ) = None
    provider_score_weight_availability: (
        Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None]
    ) = None
    provider_score_weight_reaction: Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None] = (
        None
    )
    provider_score_weight_incidents: (
        Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None]
    ) = None
    provider_score_pass_pct: Annotated[float, Field(ge=0, le=100)] | SkipJsonSchema[None] = None
    provider_score_reaction_norm_hours: Annotated[float, Field(gt=0)] | SkipJsonSchema[None] = None

    @field_validator(
        "speedtest",
        "heartbeat_interval_s",
        "config_refresh_interval_s",
        "offline_after_s",
        "school_status_measurements_count",
        "default_working_hours",
        "availability_min_pct",
        "contract_mismatch_threshold_pct",
        "contract_mismatch_window_days",
        "enrollment_code_ttl_days",
        "export_sync_max_rows",
        "export_retention_days",
        "incident_auto_close_hours",
        "agent_queue_retention_days",
        "attention_incident_unassigned_hours",
        "attention_appeal_no_answer_hours",
        "rollout_silent_days",
        "password_reset_ttl_minutes",
        "support_contact",
        "provider_score_weight_below_contract",
        "provider_score_weight_availability",
        "provider_score_weight_reaction",
        "provider_score_weight_incidents",
        "provider_score_pass_pct",
        "provider_score_reaction_norm_hours",
        mode="before",
    )
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value
