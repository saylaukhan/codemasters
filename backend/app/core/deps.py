"""Shared FastAPI dependencies: security schemes and list pagination.

Security schemes only declare authentication in OpenAPI (``auto_error=False``): the device
token is checked from T-14, the panel JWT and ``require(permission)`` from T-20.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from fastapi.security import APIKeyCookie, APIKeyHeader, HTTPBearer

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
