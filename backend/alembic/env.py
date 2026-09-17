"""Alembic environment: async engine, database URL from Settings.

Migrations are forward-only (ADR-003, CONTRIBUTING.md §6). Autogenerate compares the database
with ``app.models``; it does not know about hypertables, extensions, RLS and continuous
aggregates, so every generated revision is read and completed by hand.
"""

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# A URL set by the caller wins (tests migrate a testcontainers database); otherwise Settings.
# configparser interpolation treats "%" specially, so escape it in the URL.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))


def include_object(
    object_: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """What autogenerate compares: everything geoalchemy2 keeps, minus continuous aggregates.

    ``m_hourly`` and ``m_daily`` are TimescaleDB views created by the migration of T-19; their
    models exist only for reading, and without this autogenerate would try to create tables of
    the same name.
    """
    if getattr(object_, "info", {}).get("continuous_aggregate"):
        return False
    keep: bool = alembic_helpers.include_object(object_, name, type_, reflected, compare_to)
    return keep


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to the database (``alembic upgrade --sql``)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # PostGIS: render geoalchemy2 types with their import, skip spatial_ref_sys.
        render_item=alembic_helpers.render_item,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on an already established (sync-style) connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_item=alembic_helpers.render_item,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through a sync adapter."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
