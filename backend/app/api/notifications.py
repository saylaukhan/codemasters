"""Notification API of the panel (T-42; ТЗ п. 18; DESIGN.md §3.5, §3.23).

Every endpoint answers about the caller and no one else: the bell of one person, its counter,
its «Отметить все как прочитанные» and the stream that keeps it fresh without a page reload.
Who receives a notification at all is decided when the incident moves, by the scope of ADR-008
(``app/services/notifications.py``); here the user's own rows are selected by his id and the RLS
policy of the migration of T-42 holds that a second time.

``GET /stream`` is Server-Sent Events. It authenticates by hand instead of ``require`` because a
``yield`` dependency would hold the request's database session for as long as the connection is
open — minutes or hours — and a handful of open bells would drain the pool. The generator opens
a short session per poll and closes it again, so a stream costs a connection only while it is
actually looking. The panel reads it with ``fetch``, not ``EventSource``, so the access token
travels in the ``Authorization`` header and never in the URL (ADR-009).
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, Security, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, require
from app.auth.deps import account_blocked, load_user, unauthorized_user
from app.core.config import get_settings
from app.core.db import get_session, get_session_factory
from app.core.deps import PageParams, page_params, user_token
from app.core.errors import ApiError
from app.core.security import decode_jwt
from app.models import Notification, User
from app.schemas.notifications import NotificationListItemPage, NotificationUnreadCount
from app.services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])

PERMISSION = "notifications:read"

# How often the stream asks the database for new notifications of the user. Four seconds is far
# below what a person calls «без перезагрузки страницы» and far above what the query costs.
POLL_INTERVAL_S = 4
# A comment line keeps proxies and browsers from closing an idle stream (Caddy, deploy/Caddyfile).
KEEPALIVE_EVERY = 5

logger = logging.getLogger(__name__)


@router.get(
    "",
    summary="Уведомления пользователя, новые сверху",
    description=(
        "Только уведомления вызывающего: панель уведомлений (DESIGN.md §3.23). "
        "unread_only=true — вкладка «Непрочитанные»."
    ),
)
async def list_notifications(
    params: Annotated[PageParams, Depends(page_params)],
    user: Annotated[AuthUser, Depends(require(PERMISSION))],
    session: Annotated[AsyncSession, Depends(get_session)],
    unread_only: Annotated[bool, Query(description="Только непрочитанные")] = False,
) -> NotificationListItemPage:
    return await notifications.notification_list(
        session, user.id, unread_only=unread_only, params=params
    )


@router.get(
    "/unread-count",
    summary="Счётчик непрочитанных уведомлений",
    description="Число на колокольчике в шапке (DESIGN.md §3.5).",
)
async def get_unread_count(
    user: Annotated[AuthUser, Depends(require(PERMISSION))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationUnreadCount:
    return await notifications.unread_count(session, user.id)


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отметить все уведомления прочитанными",
    description="Ссылка «Отметить все как прочитанные» панели уведомлений (DESIGN.md §3.23).",
)
async def read_all_notifications(
    user: Annotated[AuthUser, Depends(require(PERMISSION))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await notifications.mark_all_read(session, user.id, now=datetime.now(UTC))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def stream_user(credentials: HTTPAuthorizationCredentials | None) -> AuthUser:
    """User behind the access token of the stream, on a session of its own.

    ``require`` is not used on purpose (see the module docstring): its session would stay open
    for the whole life of the connection. The checks are the same ones ``current_user`` makes —
    a valid access token of its version, an account that is not blocked — plus the permission.
    """
    if credentials is None:
        raise unauthorized_user()
    decoded = decode_jwt(
        credentials.credentials, typ="access", now=datetime.now(UTC), key=get_settings().secret_key
    )
    if decoded is None:
        raise unauthorized_user()
    user_id, version = decoded
    async with get_session_factory()() as session:
        user = await session.get(User, user_id)
        if user is None or user.token_version != version:
            raise unauthorized_user()
        if not user.is_active:
            raise account_blocked()
        auth_user = await load_user(session, user)
    if PERMISSION not in auth_user.permissions:
        raise ApiError(403, "forbidden", f"У роли нет права {PERMISSION}")
    return auth_user


async def new_notifications(user_id: int, after_id: int) -> tuple[list[dict[str, object]], int]:
    """Notifications of the user newer than ``after_id`` and the id to ask from next time.

    A session of its own, opened and closed around the one query: the stream must not hold a
    connection between polls.
    """
    async with get_session_factory()() as session:
        rows = (
            await session.execute(
                notifications.notification_rows(user_id)
                .where(Notification.id > after_id)
                .order_by(Notification.id)
            )
        ).all()
        unread = await notifications.unread_count(session, user_id)
    items = [notifications.list_item(row).model_dump(mode="json") for row in rows]
    newest = max((int(item["id"]) for item in items), default=after_id)
    return [{"notification": item, "unread": unread.unread} for item in items], newest


async def events(request: Request, user_id: int, after_id: int) -> AsyncIterator[str]:
    """SSE frames: one ``notification`` event per new row, a comment line to keep the line open."""
    quiet = 0
    while not await request.is_disconnected():
        try:
            payloads, after_id = await new_notifications(user_id, after_id)
        except Exception:
            logger.exception("notification stream of user %s failed", user_id)
            return
        for payload in payloads:
            quiet = 0
            yield f"event: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        if not payloads:
            quiet += 1
            if quiet >= KEEPALIVE_EVERY:
                quiet = 0
                yield ": keepalive\n\n"
        await asyncio.sleep(POLL_INTERVAL_S)


@router.get(
    "/stream",
    summary="Поток новых уведомлений (SSE)",
    description=(
        "text/event-stream: событие notification с полями notification и unread на каждое новое "
        "уведомление вызывающего; строка-комментарий раз в 20 секунд держит соединение. "
        "Панель подписывается через fetch с заголовком Authorization (ADR-009)."
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Поток уведомлений"}},
)
async def stream_notifications(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(user_token)],
) -> StreamingResponse:
    user = await stream_user(credentials)
    async with get_session_factory()() as session:
        latest = await session.scalar(
            select(Notification.id)
            .where(Notification.user_id == user.id)
            .order_by(Notification.id.desc())
            .limit(1)
        )
    return StreamingResponse(
        events(request, user.id, latest or 0),
        media_type="text/event-stream",
        # Caddy and nginx buffer a response by default, which would hold every frame back.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
