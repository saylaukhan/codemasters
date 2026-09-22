"""The letter of a template filled with the facts of an appeal (T-86, ТЗ п. 17, ADR-011).

A placeholder ``{{name}}`` of ``PLACEHOLDERS`` (``app/schemas/appeal_templates.py``) becomes
the value the facts hold for it, written as the panel writes it: dates and times in the zone
of the system, numbers with a decimal comma, «—» for what the line does not have. The blocks
``{{facts}}``, ``{{metrics}}`` and ``{{excerpt}}`` are the same lines the prompt of T-47 is
built from, so the model and the person read one text. Personal data never gets here: the
signature is put under the letter afterwards (``draft.py``).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from app.models import AppealTemplate
from app.schemas.appeal_templates import PLACEHOLDER, SUBJECT_MAX_LENGTH
from app.services.appeals.context import AppealFacts
from app.services.appeals.prompt import excerpt_lines, facts_lines, metric_lines, moment
from app.services.exports.report_pdf import NO_VALUE, duration, formatted


@dataclass(frozen=True)
class Letter:
    """Subject and text of a template after the facts were put in."""

    subject: str
    text: str


def placeholder_values(facts: AppealFacts) -> dict[str, str]:
    """Value of every placeholder for the facts of one appeal."""
    context = facts.context
    zone = ZoneInfo(facts.timezone)
    signed = NO_VALUE if context.contract_date is None else f"{context.contract_date:%d.%m.%Y}"
    return {
        "topic": (
            "Качество интернет-соединения"
            if context.incident_number is None
            else f"Инцидент {context.incident_number}"
        ),
        "school_code": context.school_code,
        "school_name": context.school_name,
        "provider_name": context.provider_name,
        "line_identifier": context.line_identifier or NO_VALUE,
        "contract_number": context.contract_number or NO_VALUE,
        "contract_date": signed,
        "contract_down_mbps": formatted(context.contract_down_mbps),
        "contract_up_mbps": formatted(context.contract_up_mbps),
        "period": f"{moment(context.period_from, zone)} — {moment(context.period_to, zone)}",
        "period_dates": (
            f"{context.period_from.astimezone(zone):%d.%m.%Y} — "
            f"{context.period_to.astimezone(zone):%d.%m.%Y}"
        ),
        "period_from": moment(context.period_from, zone),
        "period_to": moment(context.period_to, zone),
        "incident_number": context.incident_number or NO_VALUE,
        "measurements_count": str(context.measurements_count),
        "problem_count": str(context.problem_count),
        "outages_count": str(context.outages_count),
        "outages_duration": duration(context.outages_duration_s),
        "facts": "\n".join(f"- {line}" for line in facts_lines(facts)),
        "metrics": "\n".join(metric_lines(context)),
        "excerpt": "\n".join(excerpt_lines(facts)),
    }


def render(text: str, values: Mapping[str, str]) -> str:
    """``text`` with every known placeholder replaced; an unknown one is left as it is."""
    return PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), text)


def render_letter(template: AppealTemplate, facts: AppealFacts) -> Letter:
    """The subject and the text of ``template`` for ``facts``; the subject fits its limit."""
    values = placeholder_values(facts)
    subject = " ".join(render(template.subject, values).split())
    return Letter(subject=subject[:SUBJECT_MAX_LENGTH], text=render(template.body, values).strip())
