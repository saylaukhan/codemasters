"""Service e-mail of a provider for appeals (T-34, T-48): ``providers.appeals_email``.

The contract of T-03 already has the field; the admin reference of T-34 edits it, the sending
of appeals (T-48) reads it. It is a service address of the company, not personal data.

Revision ID: 5d2f9a3c7e18
Revises: c3b8e1f5a902
Create Date: 2026-09-18 22:00:11.408215+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d2f9a3c7e18"
down_revision: str | None = "c3b8e1f5a902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("appeals_email", sa.Text(), nullable=True))


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
