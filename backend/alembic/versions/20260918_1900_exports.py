"""Exports of measurements: the table of built files and how long they are kept (T-30).

A file is stored in ``exports.content`` until ``expires_at``; the API serves it only to the
user who made it, so the table has no RLS policy: the rows inside the file were already read
under the user's scope (ADR-008). ``settings.export_retention_days`` (7 of «Решения по
умолчанию») sets ``expires_at``; removing expired files is T-33.

Revision ID: a9e4c2d7f310
Revises: f2a6c8e04d17
Create Date: 2026-09-18 19:00:08.316402+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a9e4c2d7f310"
down_revision: str | None = "f2a6c8e04d17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "export_retention_days", sa.BigInteger(), server_default=sa.text("7"), nullable=False
        ),
    )
    op.create_table(
        "exports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rows_count", sa.BigInteger(), nullable=True),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mode IN ('raw', 'aggregates', 'school_report')", name=op.f("ck_exports_mode")
        ),
        sa.CheckConstraint(
            "format IN ('xlsx', 'csv', 'json', 'pdf')", name=op.f("ck_exports_format")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed')", name=op.f("ck_exports_status")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_exports_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exports")),
    )
    op.create_index(op.f("ix_exports_user_id"), "exports", ["user_id"], unique=False)
    op.create_index(op.f("ix_exports_expires_at"), "exports", ["expires_at"], unique=False)


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
