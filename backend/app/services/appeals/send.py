"""«Отправить»: the number, the letter to the provider, the PDF and the history (T-48, ТЗ п. 17).

Everything a draft deliberately does not do happens here. The facts are collected anew, so the
appeal argues by what the measurements say at the moment of the sending and keeps that snapshot
in ``appeals.context`` for good; the number ``ОБР-<year>-<six digits>`` comes from
``appeal_number_seq``, one sequence never reset, so a number is never reused (ADR-011).

The order is: store, then send. An appeal is written with its PDF and ``not_sent`` first and
only then the letter leaves the server, so an SMTP that hangs, refuses or is not configured at
all leaves a numbered appeal with its PDF behind instead of losing the work of the person
(«Решения по умолчанию», ТЗ п. 17). The status after the sending is «Передан поставщику» either
way: the appeal was made, the letter is a channel.

An appeal sent from the card of an incident is the handing over of that incident (T-63,
ADR-007): one in «Новый» moves to «Передан поставщику» in the same transaction as the appeal,
with a row of its history naming the number; an incident in any other status was already moved
by a person and is left as it is.
"""

import asyncio
import logging
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Sequence as DbSequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthUser
from app.core.config import Settings, get_settings
from app.models import Appeal, AppealEvent, IncidentEvent, SystemSettings
from app.schemas.appeals import AppealCreate, AppealDetail
from app.services.appeal_templates import template_for_draft
from app.services.appeals.card import appeal_detail
from app.services.appeals.context import appeal_facts
from app.services.appeals.pdf import AppealLetter, appeal_pdf
from app.services.incident_card import locked_incident
from app.services.notifications import CHANNEL_OFF, send_email
from app.services.settings import system_settings

logger = logging.getLogger(__name__)

APPEAL_NUMBERS = DbSequence("appeal_number_seq")

# An appeal is born sent to the provider: it is a letter, not a draft (ТЗ п. 19, ADR-007).
SENT_STATUS = "sent_to_provider"

NO_ADDRESS = "У поставщика не указан e-mail для обращений"

# The comment of the person travels next to the letter, never inside its text (ТЗ п. 17).
COMMENT_TITLE = "Комментарий отправителя:"

# History row of the incident the sending handed over (T-63); the number is that of the appeal.
HANDOVER_COMMENT = "Статус изменён при отправке обращения {number}"


async def appeal_number(session: AsyncSession, settings: SystemSettings, now: datetime) -> str:
    """``ОБР-<year>-<six digits>``: the year of ``now`` in the zone of the system, the digits
    from ``appeal_number_seq``, as the incidents of T-40 take theirs (ADR-011)."""
    serial = await session.scalar(select(APPEAL_NUMBERS.next_value()))
    year = now.astimezone(ZoneInfo(settings.timezone)).year
    return f"ОБР-{year}-{serial:06d}"


def pdf_name(number: str) -> str:
    """File of the appeal: its number, as the provider will file it."""
    return f"{number}.pdf"


def letter_text(text: str, user_comment: str | None) -> str:
    """Body of the e-mail: the letter and, under it, the comment of the person (ТЗ п. 17)."""
    if not user_comment:
        return text
    return f"{text}\n\n{COMMENT_TITLE}\n{user_comment}"


async def deliver(settings: Settings, appeal: Appeal, *, pdf: bytes) -> tuple[str, str | None]:
    """Fate of the letter: ``sent``, or ``not_sent`` with the reason. Nothing here is an error
    of the request — an installation without SMTP is a normal installation (ADR-011)."""
    if not settings.smtp_host:
        return "not_sent", CHANNEL_OFF
    if not appeal.recipient_email:
        return "not_sent", NO_ADDRESS
    try:
        await asyncio.to_thread(
            send_email,
            settings,
            appeal.recipient_email,
            appeal.subject,
            letter_text(appeal.text, appeal.user_comment),
            (pdf_name(appeal.number), pdf),
        )
    except (OSError, smtplib.SMTPException) as error:
        logger.warning(
            "обращение %s не ушло на %s: %s", appeal.number, appeal.recipient_email, error
        )
        return "not_sent", str(error)
    return "sent", None


async def hand_over_incident(
    session: AsyncSession, incident_id: int, number: str, user: AuthUser, *, now: datetime
) -> None:
    """«Новый» → «Передан поставщику» for the incident the appeal ``number`` is about, with the
    row of the history the card of T-41 would write; the caller commits (T-63, ADR-007). An
    incident in any other status is left untouched: a person already moved it."""
    incident = await locked_incident(session, incident_id)
    if incident.status != "new":
        return
    incident.status = SENT_STATUS
    incident.sent_to_provider_at = now
    session.add(
        IncidentEvent(
            incident_id=incident.id,
            kind="status_change",
            from_status="new",
            to_status=SENT_STATUS,
            comment=HANDOVER_COMMENT.format(number=number),
            author_user_id=user.id,
            created_at=now,
        )
    )


async def create_appeal(
    session: AsyncSession, body: AppealCreate, user: AuthUser, *, now: datetime
) -> AppealDetail:
    """Send the appeal of ``body``: a row with a number and a PDF, the incident it is about
    handed over with it, then the letter itself."""
    facts = await appeal_facts(session, body, now=now)
    # The kind of the letter is the template's: a claim stays a claim in the list and the PDF.
    template = await template_for_draft(session, body.template_id)
    settings = await system_settings(session)
    context = facts.context
    appeal = Appeal(
        number=await appeal_number(session, settings, now),
        status=SENT_STATUS,
        kind=template.kind,
        template_id=template.id,
        incident_id=body.incident_id,
        line_id=context.line_id,
        school_id=context.school_id,
        provider_id=context.provider_id,
        subject=body.subject,
        text=body.text,
        user_comment=body.user_comment,
        context=context.model_dump(mode="json"),
        recipient_email=facts.recipient_email,
        delivery_status="not_sent",
        sent_at=now,
        author_user_id=user.id,
    )
    appeal.pdf = appeal_pdf(
        AppealLetter(
            number=appeal.number,
            kind=appeal.kind,
            subject=appeal.subject,
            text=appeal.text,
            user_comment=appeal.user_comment,
            context=context,
            recipient_email=appeal.recipient_email,
            sent_at=now,
            author_name=user.full_name,
            timezone=facts.timezone,
        )
    )
    session.add(appeal)
    await session.flush()
    session.add(
        AppealEvent(
            appeal_id=appeal.id,
            kind="sent",
            to_status=SENT_STATUS,
            author_user_id=user.id,
            created_at=now,
        )
    )
    # Before the first commit: the appeal and the transition succeed or fail together (T-63).
    if body.incident_id is not None:
        await hand_over_incident(session, body.incident_id, appeal.number, user, now=now)
    await session.commit()

    delivery_status, error = await deliver(get_settings(), appeal, pdf=appeal.pdf)
    appeal.delivery_status = delivery_status
    appeal.delivery_error = error
    await session.commit()
    return await appeal_detail(session, appeal.id)
