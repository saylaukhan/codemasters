"""Declarative base of all SQLAlchemy models and the shared timestamp columns.

Constraint and index names follow ``NAMING_CONVENTION``, so a forward-only migration can refer
to any of them by a predictable name (ADR-003). ``Mapped[datetime]`` always maps to
``timestamptz``: time is stored in UTC and naive datetimes have no column type (ADR-014).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Double, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class of every table model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        int: BigInteger,
        float: Double,
        str: Text,
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }


class TimestampMixin:
    """``created_at`` / ``updated_at``: set by the database on insert, by the ORM on update."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), sort_order=100)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), sort_order=101
    )
