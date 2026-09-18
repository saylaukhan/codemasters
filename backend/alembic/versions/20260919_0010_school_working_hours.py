"""Working hours of a school and the auto-close of incidents (T-37).

``schools.working_hours`` holds the hours of one school (ADR-014); NULL means the school has no
hours of its own and the admin default of ``settings.default_working_hours`` applies. Existing
schools get a copy of the default here, so a later change of the default does not move them,
as the contract of ``PATCH /api/admin/settings`` promises. ``settings.incident_auto_close_hours``
is the value of that contract the incidents of T-40 read: 24 hours by default (ADR-007).

Revision ID: 5e2a8c4b7d19
Revises: 3c7d9e1f5a24
Create Date: 2026-09-19 00:10:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5e2a8c4b7d19"
down_revision: str | None = "3c7d9e1f5a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("working_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        "UPDATE schools SET working_hours = settings.default_working_hours "
        "FROM settings WHERE settings.id = 1"
    )
    op.add_column(
        "settings",
        sa.Column(
            "incident_auto_close_hours",
            sa.BigInteger(),
            server_default=sa.text("24"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
