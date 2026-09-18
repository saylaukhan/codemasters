"""Devices in the admin panel (T-36): ``devices.token_rotation_requested_at`` and
``settings.enrollment_code_ttl_days``.

The admin panel asks for a new token of a device; the agent sees the request in its
configuration and exchanges the token itself with ``POST /api/agent/token``, which clears the
column (ADR-005). An installation code lives ``enrollment_code_ttl_days`` days, 7 by default
(ADR-005), changed in the settings without code (ТЗ п. 20).

Revision ID: 3c7d9e1f5a24
Revises: 8b1e4f6a2c93
Create Date: 2026-09-18 23:30:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c7d9e1f5a24"
down_revision: str | None = "8b1e4f6a2c93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("token_rotation_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column(
            "enrollment_code_ttl_days", sa.BigInteger(), server_default=sa.text("7"), nullable=False
        ),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
