"""Shared fixtures: a disposable PostgreSQL 16 + TimescaleDB + PostGIS migrated to head.

The container runs the image of the ``db`` service from docker-compose.yml, so the schema is
tested on the same extensions it runs on. Docker is required; the container starts only for
tests that request a database fixture and lives for the whole test session.
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.community.postgres import PostgresContainer

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
