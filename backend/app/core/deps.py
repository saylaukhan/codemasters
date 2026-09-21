"""Shared FastAPI dependencies: security schemes, device authentication and list pagination.

``current_device`` turns ``Authorization: Device <token>`` into the row of ``devices`` (T-14,
ADR-005). ``user_token`` and ``refresh_cookie`` declare the panel authentication in OpenAPI
(``auto_error=False``: the errors are problem+json); the panel user and ``require(permission)``
live in ``app/auth`` (T-20).

This is the hottest check of the system — every agent of every school passes it on every
request — so it costs a sha256 and one lookup by primary key, and nothing else. Why the token
is not held by argon2, and what the old hashes cost until they are replaced, is in
``app/core/security.py``.
"""

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request, Security
from fastapi.security import APIKeyCookie, APIKeyHeader, HTTPBearer
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import hash_token, parse_device_token, token_needs_rehash, verify_token_async
from app.models import Device

logger = logging.getLogger(__name__)

# Agent requests: ``Authorization: Device <token>`` (ADR-005).
device_token = APIKeyHeader(
    name="Authorization",
    scheme_name="DeviceToken",
    description="Токен устройства: `Authorization: Device <token>` (ADR-005)",
    auto_error=False,
)

# Panel requests: access JWT from ``POST /api/auth/login``, kept in memory (ADR-009).
user_token = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Access-токен панели: `Authorization: Bearer <jwt>`, живёт 15 минут",
    auto_error=False,
)

# Refresh token of the panel: httpOnly cookie set by login and refresh (ADR-009).
refresh_cookie = APIKeyCookie(
    name="refresh_token",
    scheme_name="RefreshCookie",
    description="Refresh-токен панели в httpOnly cookie",
    auto_error=False,
)

# Authentication scheme of the agent: the value of the Authorization header starts with it.
DEVICE_SCHEME = "Device"
# The agent gets one wording for a missing, malformed, unknown or wrong token: telling them
# apart would let a caller check device ids without a token (ADR-005).
UNAUTHORIZED_DETAIL = "Токен устройства отсутствует или недействителен"


async def current_device(
    request: Request,
    authorization: Annotated[str | None, Security(device_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Device:
    """Device behind ``Authorization: Device <token>``; 401 unknown, 403 blocked (ADR-005).

    Every other request of the agent is derived from the row it returns: the school and the
    line of a measurement come from ``monitoring_points``, never from the request (ТЗ п. 12).
    """
    scheme, _, token = (authorization or "").partition(" ")
    parsed = parse_device_token(token.strip()) if scheme == DEVICE_SCHEME else None
    if parsed is None:
        raise unauthorized_device()
    device_id, secret = parsed
    device = await session.get(Device, device_id)
    if device is None or not await verify_token_async(secret, device.token_hash):
        raise unauthorized_device()
    # A rejected request of a known device is logged against it (app/auth/audit.py).
    request.state.device_id = device.id
    if token_needs_rehash(device.token_hash):
        await upgrade_token_hash(session, device, secret)
    # Blocking keeps the device and its history, but stops every request of the agent
    # (ТЗ п. 16, п. 20).
    if device.status != "active":
        raise ApiError(403, "device_blocked", "Устройство заблокировано администратором")
    return device


async def upgrade_token_hash(session: AsyncSession, device: Device, secret: str) -> None:
    """Put the sha256 hash of a token in place of the argon2 one it was stored with.

    A migration could not do this: the server never kept the token, only its hash, so the one
    moment it holds the token again is the request that has just proved it. The check above
    has already succeeded, so what is written is the hash of the same secret the row accepted.

    The row is found by the hash this request read and not by the id alone, and that condition
    is the point of the function. One agent keeps several requests in the air at once — the
    heartbeat, the queue it is sending, the configuration it is polling — and one of them may
    be ``POST /api/agent/token``. A rotation committed between the read above and this write
    would otherwise be overwritten here by the hash of the very token it revoked: the new
    token the agent has already saved would stop working, and the leaked one the rotation was
    pressed for would work again (ADR-005, ТЗ п. 16). When the condition matches nothing, the
    rotation has won and there is nothing left to upgrade — the row already holds a sha256
    hash of a newer token.

    Committed on its own and before the block is checked: the argon2 cost is then paid once
    per device, even by a device that is blocked and refused on every request afterwards. That
    one write bumps ``updated_at`` of the row, once in the life of a device.

    A failure is logged and swallowed. The token has been proved and the request is valid; an
    upgrade that could not be written costs the next request another argon2, which is not a
    reason to answer 500 where the answer is 204. The rollback expires the instance, so the
    device is read again before the caller looks at its status.
    """
    previous, upgraded = device.token_hash, hash_token(secret)
    try:
        # ``RETURNING`` says whether the condition found the row: the answer is needed before
        # the object is touched, and the statement goes to PostgreSQL either way (ADR-002).
        result = await session.execute(
            update(Device)
            .where(Device.id == device.id, Device.token_hash == previous)
            .values(token_hash=upgraded)
            .returning(Device.id)
            .execution_options(synchronize_session=False)
        )
        written = result.scalar_one_or_none()
        await session.commit()
    except SQLAlchemyError:
        logger.warning("перехэш токена устройства %s не сохранён", device.id, exc_info=True)
        await session.rollback()
        await session.refresh(device)
        return
    if written is None:
        logger.info("токен устройства %s сменился во время запроса, перехэш пропущен", device.id)
        return
    # The row and the object hold the same value again, and it is not a pending change: the
    # commit of the endpoint must not write this column a second time, unconditionally.
    set_committed_value(device, "token_hash", upgraded)
    logger.info("токен устройства %s перехэширован в формат sha256", device.id)


def unauthorized_device() -> ApiError:
    return ApiError(401, "unauthorized", UNAUTHORIZED_DETAIL, {"WWW-Authenticate": DEVICE_SCHEME})


MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    """Requested page of a list; ``offset`` is ready for ``OFFSET`` in SQL."""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1, description="Номер страницы, с 1")] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Размер страницы")] = 20,
) -> PageParams:
    """Query parameters ``page`` and ``page_size`` of every paginated endpoint."""
    return PageParams(page=page, page_size=page_size)
