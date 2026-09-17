"""System settings: the single row of ``settings`` with the measurement servers (T-05).

LibreSpeed and the ndt7 fallback (ADR-012); ``make seed`` stores the initial addresses. The other
values of the admin settings contract arrive as columns with the tasks that use them (T-17, T-37).

Revision ID: 12d8fd66ef0b
Revises: 72bc0e369aa3
Create Date: 2026-09-17 16:12:37.324352+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12d8fd66ef0b"
down_revision: str | None = "72bc0e369aa3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("librespeed_url", sa.Text(), nullable=False),
        sa.Column("ndt7_url", sa.Text(), nullable=True),
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
        sa.CheckConstraint("id = 1", name=op.f("ck_settings_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settings")),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
