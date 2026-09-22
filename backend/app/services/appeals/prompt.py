"""Prompt of the appeal: the facts of the context, the filled template and nothing else (T-47,
T-86, ADR-011, plan.md §8).

Everything the model sees is built here out of ``AppealFacts`` and the template of the admin
panel: School ID, the school, the provider, the contract, the period, the aggregates against
the thresholds, the downtime, the excerpt of the measurements, then the letter of the template
filled with the same facts and the instructions the template carries. Names, positions, phones
and e-mails of ``school_contacts`` never get here — they are put into the ready text after the
generation (``draft.py``), and the test of T-47 reads the prompt to prove it. Free text of the
user is not in the prompt either: a draft is asked for by facts, and his comment travels next to
the sent appeal (ТЗ п. 17, T-48).

The lines are Russian and are read by a person too: the same facts fill the template the editor
opens with when the model is silent. Numbers and durations are written as the panel writes them
(``web/src/lib/format.ts``), the words of the columns and of the statuses are those of an export
(ADR-013).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas.appeals import AppealContext
from app.services.appeals.context import AppealFacts, MeasurementExcerpt
from app.services.exports.columns import COLUMN_TITLES, VALUE_LABELS
from app.services.exports.report_pdf import NO_VALUE, duration, formatted

# What the model is for and what it may not do: no invented numbers, no invented people.
SYSTEM = (
    "Ты готовишь официальные письма поставщикам интернета для управления образования "
    "Восточно-Казахстанской области. Пиши по-русски, деловым тоном, без эмоций и угроз. "
    "Опирайся только на факты из запроса: не добавляй цифры, названия и обстоятельства, "
    "которых в нём нет. Ответ — только текст письма в Markdown. Не подписывай письмо: "
    "ФИО, должности, телефоны и e-mail подставляются после генерации."
)

TASK = "Составь текст официального письма поставщику интернета по фактам ниже."

# The letter of the template, filled with the facts, is the structure the model keeps
# (plan.md §8): who to and about what, the contract, the fact against the threshold and against
# the contract, the demand and the term of the answer.
LETTER_TITLE = (
    "Шаблон письма, заполненный фактами. Сохрани его структуру, реквизиты, цифры и "
    "требования; изложи связным деловым текстом:"
)
INSTRUCTIONS_TITLE = "Дополнительные требования к письму:"
NO_SIGNATURE = "Подпись не добавляй."

# Threshold of each metric and how it is read: speeds from below, delays and losses from above.
METRIC_LIMITS: dict[str, tuple[str, str]] = {
    "download_mbps": ("download_min_mbps", "не ниже"),
    "upload_mbps": ("upload_min_mbps", "не ниже"),
    "ping_ms": ("ping_max_ms", "не выше"),
    "jitter_ms": ("jitter_max_ms", "не выше"),
    "packet_loss_pct": ("packet_loss_max_pct", "не выше"),
}

# Metrics the contract promises a value for (ТЗ п. 14, ADR-003).
CONTRACT_VALUES = {"download_mbps": "contract_down_mbps", "upload_mbps": "contract_up_mbps"}

QUALITY_TITLES = VALUE_LABELS["quality_status"]


def moment(value: datetime, zone: ZoneInfo) -> str:
    """Moment in the time of the school: storage is UTC, a letter is local (ADR-014)."""
    return f"{value.astimezone(zone):%d.%m.%Y %H:%M}"


def facts_lines(facts: AppealFacts) -> list[str]:
    """Who the appeal is about, by what contract and over which period."""
    context = facts.context
    zone = ZoneInfo(facts.timezone)
    signed = NO_VALUE if context.contract_date is None else f"{context.contract_date:%d.%m.%Y}"
    lines = [
        f"School ID: {context.school_code}",
        f"Школа: {context.school_name}",
        f"Поставщик: {context.provider_name}",
        f"Линия: {context.line_identifier or NO_VALUE}",
        f"Договор: {context.contract_number or NO_VALUE} от {signed}",
        f"Период: {moment(context.period_from, zone)} — {moment(context.period_to, zone)} "
        f"({facts.timezone})",
        f"Замеров за период: {context.measurements_count}, "
        f"из них с нарушением: {context.problem_count}",
        f"Простоев: {context.outages_count}, суммарно {duration(context.outages_duration_s)}",
    ]
    if context.incident_number is not None:
        lines.insert(0, f"Инцидент: {context.incident_number}")
    return lines


def metric_lines(context: AppealContext) -> list[str]:
    """Fact of every metric next to its threshold and to the value of the contract (ТЗ п. 11)."""
    lines = []
    for metric, (limit_field, rule) in METRIC_LIMITS.items():
        stats = getattr(context, metric)
        parts = [
            "нет значений за период"
            if stats is None
            else f"среднее {formatted(stats.avg)}, минимум {formatted(stats.min)}, "
            f"максимум {formatted(stats.max)}",
            f"порог {rule} {formatted(getattr(context.thresholds, limit_field))}",
        ]
        contract_field = CONTRACT_VALUES.get(metric)
        promised = None if contract_field is None else getattr(context, contract_field)
        if promised is not None:
            parts.append(f"по договору не ниже {formatted(promised)}")
        lines.append(f"- {COLUMN_TITLES[metric]}: {'; '.join(parts)}")
    return lines


def excerpt_line(item: MeasurementExcerpt, zone: ZoneInfo) -> str:
    values = [
        formatted(item.download_mbps),
        formatted(item.upload_mbps),
        formatted(item.ping_ms),
        formatted(item.jitter_ms),
        formatted(item.packet_loss_pct),
    ]
    status = NO_VALUE if item.quality_status is None else QUALITY_TITLES[item.quality_status]
    return f"- {moment(item.measured_at, zone)}: {' / '.join(values)} — {status}"


def excerpt_lines(facts: AppealFacts) -> list[str]:
    """Measurements quoted to the model; a period without measurements says so (plan.md §8)."""
    if not facts.excerpt:
        return ["Выдержка замеров: за период замеров нет."]
    zone = ZoneInfo(facts.timezone)
    return [
        "Выдержка замеров (время, Download / Upload / Ping / Jitter / Packet Loss, статус):",
        *(excerpt_line(item, zone) for item in facts.excerpt),
    ]


def build_prompt(facts: AppealFacts, *, letter: str, instructions: str | None = None) -> str:
    """The whole prompt: the task, the facts, the measurements, the filled letter of the
    template and the instructions of the template (T-86)."""
    return "\n".join(
        [
            TASK,
            "",
            "Факты обращения:",
            *(f"- {line}" for line in facts_lines(facts)),
            "",
            "Показатели за период (факт против порога и против договора):",
            *metric_lines(facts.context),
            "",
            *excerpt_lines(facts),
            "",
            LETTER_TITLE,
            "",
            letter,
            "",
            *([INSTRUCTIONS_TITLE, instructions.strip(), ""] if instructions else []),
            NO_SIGNATURE,
        ]
    )
