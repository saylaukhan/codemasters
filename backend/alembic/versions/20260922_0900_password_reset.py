"""«Забыли пароль?» of the sign-in screen: one-time reset links (T-65; docs/design/README.md §4.6).

``password_reset_tokens`` is the closest relative of ``enrollment_codes`` (ADR-005): the secret
itself is never stored, only its sha256; the id of the row is the part of the link that finds
the hash back, ``expires_at`` bounds it and ``used_at`` makes it one-time. The row has no
visibility scope — the endpoints that read it answer a person who is not signed in yet — so it
carries no RLS policy; the default privileges of the migration of T-20 give the panel role its
SELECT, INSERT and UPDATE.

Two settings join it instead of constants in the code (ТЗ п. 11, п. 20; ADR-004):
``password_reset_ttl_minutes`` is the 30 minutes the link lives of docs/tasks/README.md T-65,
and ``support_contact`` is what the sign-in screen shows instead of the link on an installation
without SMTP. Empty by default: an installation that has not filled it shows no contact at all.

Revision ID: d5b9a3c71e42
Revises: b2f7c4a91d38
Create Date: 2026-09-22 09:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5b9a3c71e42"
down_revision: str | None = "b2f7c4a91d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
    )
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"])
    op.add_column(
        "settings",
        sa.Column(
            "password_reset_ttl_minutes",
            sa.BigInteger(),
            server_default=sa.text("30"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column("support_contact", sa.Text(), server_default=sa.text("''"), nullable=False),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
