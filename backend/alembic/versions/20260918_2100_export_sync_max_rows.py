"""Background exports (T-33): the number of rows above which an export is built by Celery.

An export of more rows than ``settings.export_sync_max_rows`` (10 000 of «Решения по
умолчанию») and every PDF are built in the background; smaller ones stay in the request.

Revision ID: c3b8e1f5a902
Revises: a9e4c2d7f310
Create Date: 2026-09-18 21:00:04.112930+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3b8e1f5a902"
down_revision: str | None = "a9e4c2d7f310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "export_sync_max_rows",
            sa.BigInteger(),
            server_default=sa.text("10000"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
