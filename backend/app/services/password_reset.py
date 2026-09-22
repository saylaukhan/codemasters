"""«Забыли пароль?»: the one-time link, the letter and the new password (T-65; §4.6 дизайна).

The request of a link answers the same 204 whatever the e-mail is — unknown, known, blocked, or
an installation without SMTP — so the endpoint never tells a stranger which addresses have an
account. The branch that has nothing to send spends the time of a password check
(``burn_password_check_async``) for the same reason the sign-in of an unknown e-mail does: the
answer must not be faster for an address that does not exist.

The link itself is the token of a device under another name (``app/core/security.py``): 256
random bits with the id of its row in front, stored as sha256 only and compared in constant
time. ``expires_at`` bounds it, ``used_at`` makes it one-time, and a successful change spends
every other unused link of that user — one request, one password.

A refused link is always the same problem type: the panel cannot tell «устарела» from «не та»,
and a wrong token is worth no more than a wrong password. The letter goes out after the row is
committed; an SMTP that refuses it is logged and changes no answer, as the sending of an appeal
does (ADR-011).
"""

import asyncio
import logging
import smtplib
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.audit import AuditEntry, client_ip
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import (
    burn_password_check_async,
    format_reset_token,
    hash_password_async,
    hash_token,
    new_reset_secret,
    parse_reset_token,
    verify_token,
)
from app.models import PasswordResetToken, User
from app.schemas.auth import LoginInfo, PasswordResetConfirm, PasswordResetRequest
from app.services.notifications import send_email
from app.services.settings import system_settings

logger = logging.getLogger(__name__)

INVALID_TOKEN = "invalid_reset_token"
INVALID_TOKEN_DETAIL = "Ссылка недействительна или устарела — запросите новую"

# Path of the panel the link points at (``web/src/app/App.tsx``).
RESET_PATH = "/password-reset"

LETTER_SUBJECT = "Смена пароля в системе мониторинга интернета ВКО"
LETTER_TEXT = (
    "Чтобы задать новый пароль, откройте ссылку:\n{link}\n\n"
    "Ссылка действует {minutes} мин. и только один раз.\n"
    "Если смену пароля запрашивали не вы, это письмо можно не читать."
)

# What the audit record of each of the two actions says happened (T-39).
LINK_ISSUED = "выдана"
LINK_USED = "использована"


def invalid_token() -> ApiError:
    """One refusal for every bad link: expired, spent and wrong look the same (ADR-009)."""
    return ApiError(400, INVALID_TOKEN, INVALID_TOKEN_DETAIL)


def reset_link(settings: Settings, token: str) -> str:
    """Address of the panel with the token in the query; the panel serves ``/password-reset``."""
    return f"{settings.api_base_url.rstrip('/')}{RESET_PATH}?token={token}"


def record(session: AsyncSession, request: Request, user: User, state: str) -> None:
    """Add the ``password_reset`` audit record of this action (no commit); never the token."""
    entry = AuditEntry(
        action="password_reset",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        user_email=user.email,
        changes={"reset_link": {"new": state}},
        ip=client_ip(request.scope),
    )
    session.add(entry.row())


async def send_link(settings: Settings, address: str, token: str, minutes: int) -> None:
    """The letter with the link; an SMTP that refuses it is logged, never answered with."""
    text = LETTER_TEXT.format(link=reset_link(settings, token), minutes=minutes)
    try:
        await asyncio.to_thread(send_email, settings, address, LETTER_SUBJECT, text)
    except (OSError, smtplib.SMTPException) as error:
        # Neither the address nor the token gets into the log: only what went wrong.
        logger.warning("ссылка на смену пароля не отправлена: %s", error)


async def request_reset(
    session: AsyncSession, request: Request, body: PasswordResetRequest, *, now: datetime
) -> None:
    """Issue a link and send it, or do nothing at all: the endpoint answers the same either way."""
    settings = get_settings()
    email = body.email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    if not settings.smtp_host or user is None or not user.is_active:
        await burn_password_check_async(email)
        return
    minutes = (await system_settings(session)).password_reset_ttl_minutes
    secret = new_reset_secret()
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(secret),
        expires_at=now + timedelta(minutes=minutes),
    )
    session.add(row)
    await session.flush()
    record(session, request, user, LINK_ISSUED)
    await session.commit()
    await send_link(settings, user.email, format_reset_token(row.id, secret), minutes)


async def confirm_reset(
    session: AsyncSession, request: Request, body: PasswordResetConfirm, *, now: datetime
) -> None:
    """Set the new password of the owner of the link and spend every link he has."""
    parsed = parse_reset_token(body.token)
    if parsed is None:
        raise invalid_token()
    token_id, secret = parsed
    row = await session.get(PasswordResetToken, token_id)
    if row is None or not verify_token(secret, row.token_hash):
        raise invalid_token()
    if row.used_at is not None or row.expires_at <= now:
        raise invalid_token()
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise invalid_token()
    user.password_hash = await hash_password_async(body.password.get_secret_value())
    # Sessions opened with the old password end now, as an administrative reset ends them
    # (``app/services/users.py``): ``current_user`` compares ``token_version`` on each request.
    user.token_version += 1
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    record(session, request, user, LINK_USED)
    await session.commit()


async def login_info(session: AsyncSession) -> LoginInfo:
    """Whether the sign-in screen shows the link or the contact of the administrator."""
    settings = await system_settings(session)
    return LoginInfo(
        password_reset_available=bool(get_settings().smtp_host),
        support_contact=settings.support_contact,
    )
