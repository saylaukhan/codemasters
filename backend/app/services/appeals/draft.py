"""Draft of an appeal: fill the template, ask the model, then sign the contacts under the answer
(T-47, T-60, ТЗ п. 17).

The order is the point of ADR-011. The template of the admin panel is filled with facts only
(``template.py``), the prompt is built from the facts and the filled letter (``prompt.py``),
the model answers, and only then the responsible person of ``school_contacts`` is put under the
letter — with the phone only for a role that has ``contacts:phone`` (ТЗ п. 15, ADR-008), the
same rule the school card follows.

A model that is not configured or does not answer is not an error of the endpoint: the 503 of
the adapter (``app/services/llm``) becomes ``ai_generated=false`` and the filled template with
the same signature, so the editor opens with something to edit instead of an error across the
whole screen (ADR-011). Nothing here is stored and no number is assigned: the sending, the
number, the letter and the PDF are T-48.
"""

import logging
from datetime import datetime
from http import HTTPStatus

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthUser
from app.core.errors import ApiError
from app.models import SchoolContact
from app.schemas.appeals import AppealDraft, AppealDraftRequest
from app.services.appeal_templates import template_for_draft
from app.services.appeals.context import appeal_facts
from app.services.appeals.prompt import SYSTEM, build_prompt
from app.services.appeals.template import render_letter
from app.services.llm import get_provider
from app.services.school_card import contact_detail

logger = logging.getLogger(__name__)

# Phone of a responsible person of a school (ТЗ п. 15), as ``app/api/schools.py`` names it.
PHONE_PERMISSION = "contacts:phone"

NO_CONTACT = "Ответственное лицо школы: не указано в карточке школы"


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
    template = await template_for_draft(session, body.template_id)
    letter = render_letter(template, facts)
    signed = await signature(
        session, facts.context.school_id, show_phone=PHONE_PERMISSION in user.permissions
    )
    ai_generated = True
    try:
        text = await get_provider().generate(
            build_prompt(facts, letter=letter.text, instructions=template.ai_instructions),
            system=SYSTEM,
        )
    except ApiError as error:
        # Every 503 of this call comes from the adapter, and an installation without a model is
        # a normal installation: the editor opens with the filled template (ADR-011).
        if error.status != HTTPStatus.SERVICE_UNAVAILABLE:
            raise
        logger.info("appeal draft without the model: %s", error.detail)
        ai_generated = False
        text = letter.text
    return AppealDraft(
        subject=letter.subject,
        text=f"{text.strip()}\n\n{signed}",
        ai_generated=ai_generated,
        recipient_email=facts.recipient_email,
        template_id=template.id,
        template_name=template.name,
        kind=template.kind,
        context=facts.context,
    )
