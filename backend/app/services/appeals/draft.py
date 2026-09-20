"""Draft of an appeal: ask the model, then sign the contacts under the answer (T-47, ТЗ п. 17).

The order is the point of ADR-011. The prompt is built from facts only (``prompt.py``), the
model answers, and only then the responsible person of ``school_contacts`` is put under the
letter — with the phone only for a role that has ``contacts:phone`` (ТЗ п. 15, ADR-008), the
same rule the school card follows.

A model that is not configured or does not answer is not an error of the endpoint: the 503 of
the adapter (``app/services/llm``) becomes ``ai_generated=false`` and a template with the same
facts and the same signature, so the editor opens with something to edit instead of an error
across the whole screen (ADR-011). Nothing here is stored and no number is assigned: the
sending, the number, the letter and the PDF are T-48.
"""

import logging
from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthUser
from app.core.errors import ApiError
from app.models import SchoolContact
from app.schemas.appeals import AppealDraft, AppealDraftRequest
from app.services.appeals.context import AppealFacts, appeal_facts
from app.services.appeals.prompt import (
    SYSTEM,
    build_prompt,
    facts_lines,
    metric_lines,
)
from app.services.llm import get_provider
from app.services.school_card import contact_detail

logger = logging.getLogger(__name__)

# Phone of a responsible person of a school (ТЗ п. 15), as ``app/api/schools.py`` names it.
PHONE_PERMISSION = "contacts:phone"

NO_CONTACT = "Ответственное лицо школы: не указано в карточке школы"

# Letter the person writes himself when the model is silent: the facts are already in it.
TEMPLATE_GREETING = "Уважаемые коллеги!"
TEMPLATE_DEMAND = (
    "Просим устранить нарушение качества услуги и сообщить о принятых мерах в срок, "
    "установленный договором."
)


def subject(facts: AppealFacts) -> str:
    """Subject of the letter: what it is about, the School ID and the period (ТЗ п. 17)."""
    context = facts.context
    zone = ZoneInfo(facts.timezone)
    period = (
        f"{context.period_from.astimezone(zone):%d.%m.%Y} — "
        f"{context.period_to.astimezone(zone):%d.%m.%Y}"
    )
    about = (
        "Качество интернет-соединения"
        if context.incident_number is None
        else f"Инцидент {context.incident_number}"
    )
    return f"{about}: {context.school_code}, {context.school_name}, период {period}"


def empty_template(facts: AppealFacts) -> str:
    """Draft without the model: the facts of the appeal in the shape of a letter (ADR-011)."""
    context = facts.context
    return "\n".join(
        [
            f"**{context.provider_name}**",
            "",
            TEMPLATE_GREETING,
            "",
            "По данным мониторинга качества интернет-соединения:",
            "",
            *(f"- {line}" for line in facts_lines(facts)),
            "",
            "Показатели за период:",
            "",
            *metric_lines(context),
            "",
            TEMPLATE_DEMAND,
        ]
    )


async def signature(session: AsyncSession, school_id: int, *, show_phone: bool) -> str:
    """Contacts under the letter, put in after the generation and never before it (ADR-011).

    The first responsible person of the card answers for the school; a school without contacts
    gets a line to fill in, not an invented name. The phone is shown only to a role that may
    see it (``contact_detail``, ТЗ п. 15).
    """
    contact = await session.scalar(
        select(SchoolContact)
        .where(SchoolContact.school_id == school_id)
        .order_by(SchoolContact.id)
        .limit(1)
    )
    if contact is None:
        return f"---\n\n{NO_CONTACT}"
    detail = contact_detail(contact, show_phone=show_phone)
    who = detail.full_name if detail.position is None else f"{detail.full_name}, {detail.position}"
    lines = [f"Ответственное лицо школы: {who}"]
    if detail.phone is not None:
        lines.append(f"Телефон: {detail.phone}")
    if detail.email is not None:
        lines.append(f"E-mail: {detail.email}")
    return "---\n\n" + "\n".join(lines)


async def appeal_draft(
    session: AsyncSession, body: AppealDraftRequest, user: AuthUser, *, now: datetime
) -> AppealDraft:
    """Editable draft of an appeal to the provider of the line (ТЗ п. 17, plan.md §8)."""
    facts = await appeal_facts(session, body, now=now)
    signed = await signature(
        session, facts.context.school_id, show_phone=PHONE_PERMISSION in user.permissions
    )
    ai_generated = True
    try:
        text = await get_provider().generate(build_prompt(facts), system=SYSTEM)
    except ApiError as error:
        # Every 503 of this call comes from the adapter, and an installation without a model is
        # a normal installation: the editor opens with the template of the same facts (ADR-011).
        if error.status != HTTPStatus.SERVICE_UNAVAILABLE:
            raise
        logger.info("appeal draft without the model: %s", error.detail)
        ai_generated = False
        text = empty_template(facts)
    return AppealDraft(
        subject=subject(facts),
        text=f"{text.strip()}\n\n{signed}",
        ai_generated=ai_generated,
        recipient_email=facts.recipient_email,
        context=facts.context,
    )
