"""Rate limit of the agent API (ТЗ п. 12, п. 3; plan.md §13).

``RateLimitMiddleware`` (installed in ``app/main.py`` around the audit) counts the requests of
one device in Redis and answers 429 ``too_many_requests`` with ``Retry-After`` once the window
is full; the agent waits the pause out instead of hammering the server
(``agent/internal/api/retry.go``, T-11). Requests without a device token are counted per
address: registration is the only one of them, and its installation codes must not be findable
by brute force (ADR-005). Panel requests are not counted here.

The counter is a fixed window: ``INCR`` of a key that expires with the window, so the pause the
answer asks for is the life left of that key. A Redis that does not answer lets the request
through — a measurement is not worth losing to a broken counter (ADR-006). The refusal goes to
``audit_log`` as ``transfer_error`` once per window (T-39): the limit exists to stop a flood,
not to turn it into a flood of records.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.auth.audit import AuditEntry, client_ip, write_entry
from app.core.config import get_settings
from app.core.deps import DEVICE_SCHEME
from app.core.errors import problem_response, status_problem
from app.core.security import parse_device_token

logger = logging.getLogger(__name__)

# The only endpoint of the agent that carries no token yet (ADR-005).
REGISTER_PATH = "/api/devices/register"

TOO_MANY_DETAIL = "Слишком много запросов: повторите через {pause} с"
TOO_MANY_TYPE = "too_many_requests"

# Hits and the seconds left of the window, as the counter reports them.
type Counter = Callable[[str, int], Awaitable[tuple[int, int]]]


@dataclass(frozen=True)
class Counted:
    """Who the request is counted against and how many are allowed in one window."""

    key: str
    limit: int
    # Known only for a request with a token: the record of the refusal names the device (T-39).
    device_id: int | None = None


class RedisCounter:
    """Fixed window in Redis: one round trip per request.

    ``EXPIRE ... NX`` sets the life of the key only when it has none, so the window starts with
    its first hit and is not pushed forward by the ones that follow.
    """

    def __init__(self, url: str) -> None:
        self.redis: Redis = Redis.from_url(url)

    async def __call__(self, key: str, window_s: int) -> tuple[int, int]:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_s, nx=True)
            pipe.ttl(key)
            hits, _, ttl = await pipe.execute()
        return int(hits), int(ttl)


def counted_device(scope: Scope) -> int | None:
    """Device id of ``Authorization: Device <token>``, without checking the secret.

    The counter needs a key, not an authenticated device: verifying the argon2 hash first would
    make the check the flood it is there to stop. A made-up id therefore gets a window of its
    own — and the 401 of ``current_device`` behind it (ADR-005).
    """
    scheme, _, token = Headers(scope=scope).get("Authorization", "").partition(" ")
    if scheme != DEVICE_SCHEME:
        return None
    parsed = parse_device_token(token.strip())
    return None if parsed is None else parsed[0]


def counted(scope: Scope) -> Counted | None:
    """What the request is counted against, or ``None`` when the limit does not apply."""
    settings = get_settings()
    device_id = counted_device(scope)
    if device_id is not None:
        limit = settings.agent_rate_limit
        return Counted(f"rl:device:{device_id}", limit, device_id) if limit > 0 else None
    if scope["path"] == REGISTER_PATH:
        address = client_ip(scope)
        limit = settings.agent_register_rate_limit
        if address is not None and limit > 0:
            return Counted(f"rl:address:{address}", limit)
    return None


class RateLimitMiddleware:
    """Middleware refusing the requests of an agent over its limit (T-51).

    Tests put their own counter in ``app.state.rate_limit_counter``; without it the window
    lives in the Redis of ``Settings.redis_url``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.redis_counter: Counter | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        against = counted(scope) if scope["type"] == "http" else None
        if against is None:
            await self.app(scope, receive, send)
            return
        window_s = get_settings().agent_rate_limit_window_s
        hits, ttl = await self.count(scope, against.key, window_s)
        if hits <= against.limit:
            await self.app(scope, receive, send)
            return
        # A key without a life left (the window expired between INCR and TTL) asks for a whole one.
        await self.refuse(scope, receive, send, against, ttl if ttl > 0 else window_s)
        # Only the request that opens the window is recorded: the ones behind it are the flood.
        if hits == against.limit + 1:
            await self.record(scope, against)

    async def count(self, scope: Scope, key: str, window_s: int) -> tuple[int, int]:
        """Hits of ``key`` in the current window; a counter that fails lets the request pass."""
        counter: Counter | None = getattr(scope["app"].state, "rate_limit_counter", None)
        if counter is None:
            if self.redis_counter is None:
                self.redis_counter = RedisCounter(get_settings().redis_url)
            counter = self.redis_counter
        try:
            return await counter(key, window_s)
        except (RedisError, OSError):
            logger.warning("лимит запросов не проверен: счётчик %s не ответил", key, exc_info=True)
            return 0, 0

    async def refuse(
        self, scope: Scope, receive: Receive, send: Send, against: Counted, pause: int
    ) -> None:
        """Answer 429 with the pause the agent must wait out (ADR-009)."""
        problem = status_problem(429, TOO_MANY_TYPE, TOO_MANY_DETAIL.format(pause=pause))
        response = problem_response(Request(scope, receive), problem, {"Retry-After": str(pause)})
        await response(scope, receive, send)

    async def record(self, scope: Scope, against: Counted) -> None:
        """Write the refusal to the audit log as a transfer error (ТЗ п. 12, T-39)."""
        application: Starlette = scope["app"]
        await write_entry(
            application,
            AuditEntry(
                action="transfer_error",
                entity_type="device",
                entity_id=against.device_id,
                error_type=TOO_MANY_TYPE,
                ip=client_ip(scope),
            ),
        )
