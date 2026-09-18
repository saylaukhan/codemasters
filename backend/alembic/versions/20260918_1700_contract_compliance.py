"""Sustained mismatch with the contract: the rule in ``settings``, the result on ``lines``.

The rule of «Решения по умолчанию» (ТЗ п. 14) — more than 50 % of the measurements of the main
line over 7 days below the contract speed — is two columns of ``settings`` changed in the admin
panel, not code (T-29, T-37). The periodic recompute writes its result onto the line: the share
below the contract, the flag, the window it was counted over and when; NULL until the first
recompute or while there is nothing to compare. The columns sit on ``lines``, so the RLS policy
of the table covers them too (ADR-008).

Revision ID: f2a6c8e04d17
Revises: e7c3a9d15b42
Create Date: 2026-09-18 17:00:21.408133+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a6c8e04d17"
down_revision: str | None = "e7c3a9d15b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "contract_mismatch_threshold_pct",
            sa.Double(),
            server_default=sa.text("50"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "contract_mismatch_window_days",
            sa.BigInteger(),
            server_default=sa.text("7"),
            nullable=False,
        ),
    )
    op.add_column("lines", sa.Column("compliance_below_pct", sa.Double(), nullable=True))
    op.add_column("lines", sa.Column("compliance_sustained_mismatch", sa.Boolean(), nullable=True))
    op.add_column("lines", sa.Column("compliance_window_days", sa.BigInteger(), nullable=True))
    op.add_column(
        "lines", sa.Column("compliance_checked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
