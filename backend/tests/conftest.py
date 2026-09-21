"""Shared fixtures: a disposable PostgreSQL 16 + TimescaleDB + PostGIS migrated to head and
an HTTP client of the application bound to it.

The rate limit of the agent API (T-51) counts in ``MemoryCounter`` instead of Redis: tests
need no broker, and a test of the limit narrows the settings and reads the counter back.

The container runs the image of the ``db`` service from docker-compose.yml, so the schema is
tested on the same extensions it runs on. Docker is required; the container starts only for
tests that request a database fixture and lives for the whole test session.
"""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import nullcontext
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.core.db import get_session
from app.main import create_app

# Settings the application reads outside the database (the JWT key, the API address); set in
# the environment they override .env, so every run signs tokens with the same test key. The
# database of the tests is the container below, never DATABASE_URL.
for name, value in {
    "DATABASE_URL": "postgresql+asyncpg://unused:unused@localhost:1/unused",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "test-only-secret-key",
    "API_BASE_URL": "http://localhost:8000",
    "SPEEDTEST_URL": "http://localhost:8080",
}.items():
    os.environ[name] = value

POSTGRES_IMAGE = "timescale/timescaledb-ha:pg16"
ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Start the database container and apply every migration with ``alembic upgrade head``."""
    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        # No alembic.ini: its logging config would replace pytest's log handlers.
        config = Config()
        config.set_main_option("script_location", str(ALEMBIC_DIR))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(config, "head")
        yield url


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    """Session inside a transaction that is rolled back after the test: tests do not see each
    other's rows. ``commit()`` in a test releases a savepoint, not the outer transaction."""
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as db_session:
            yield db_session
        await transaction.rollback()
    await engine.dispose()


class MemoryCounter:
    """Counter of ``RateLimitMiddleware`` for tests: a window per key, without Redis (T-51).

    The window never expires by itself — one test is shorter than any of them — so the seconds
    it reports left are the whole window. ``fails`` turns the counter into a Redis that does
    not answer.
    """

    def __init__(self) -> None:
        self.hits: dict[str, int] = {}
        self.fails = False

    async def __call__(self, key: str, window_s: int) -> tuple[int, int]:
        if self.fails:
            raise RedisError("счётчик недоступен")
        self.hits[key] = self.hits.get(key, 0) + 1
        return self.hits[key], window_s


@pytest.fixture
def rate_limit_counter() -> MemoryCounter:
    """Counter the application of ``api_client`` counts its rate limit in (T-51)."""
    return MemoryCounter()


@pytest.fixture
async def api_client(
    session: AsyncSession, rate_limit_counter: MemoryCounter
) -> AsyncIterator[AsyncClient]:
    """Application answering over ASGI on the session of the test: rows an endpoint writes are
    visible to the test and disappear with its transaction; so do the audit records."""
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    application.state.audit_sessions = lambda: nullcontext(session)
    # The rate limit of T-51 counts in memory instead of Redis: the limits themselves are wide
    # enough for any test, and a test of the limit narrows them on the settings.
    application.state.rate_limit_counter = rate_limit_counter
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def export_queue(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Exports ``POST /api/exports`` hands to Celery (T-33), instead of Redis: the test builds
    them itself with ``build_pending_export``, as the worker would."""
    queued: list[int] = []
    monkeypatch.setattr("app.api.exports.enqueue_build", queued.append)
    return queued


@pytest.fixture(autouse=True)
def detection_queue(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Lines the agent API hands to the incident detection (T-40), instead of Redis: a test
    that needs the detection runs ``detect_line`` itself, as the worker would."""
    queued: list[int] = []
    monkeypatch.setattr("app.api.agent.enqueue_detection", queued.append)
    return queued
