"""Shared FastAPI dependencies: security schemes, device authentication and list pagination.

``current_device`` turns ``Authorization: Device <token>`` into the row of ``devices`` (T-14,
ADR-005). ``user_token`` and ``refresh_cookie`` declare the panel authentication in OpenAPI
(``auto_error=False``: the errors are problem+json); the panel user and ``require(permission)``
live in ``app/auth`` (T-20).
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request, Security
from fastapi.security import APIKeyCookie, APIKeyHeader, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import parse_device_token, verify_secret
from app.models import Device

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
    if device is None or not verify_secret(secret, device.token_hash):
        raise unauthorized_device()
    # A rejected request of a known device is logged against it (app/auth/audit.py).
    request.state.device_id = device.id
    # Blocking keeps the device and its history, but stops every request of the agent
    # (ТЗ п. 16, п. 20).
    if device.status != "active":
        raise ApiError(403, "device_blocked", "Устройство заблокировано администратором")
    return device


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
