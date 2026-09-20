"""Self-update channel of a device: ``devices.update_channel`` (T-50; ТЗ п. 20, plan.md §4.6).

A release is published to a channel: the pilot devices take it first and the rest only after it
is promoted to ``stable`` (``agent_releases``, T-17). Until now every agent was on the stable
channel, so existing devices keep exactly that; the administrator moves a pilot computer with
``PATCH /api/devices/{id}``.

Revision ID: 6d3f8a1c9b42
Revises: 7c4d9e2b1a63
Create Date: 2026-09-21 01:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d3f8a1c9b42"
down_revision: str | None = "7c4d9e2b1a63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("update_channel", sa.Text(), server_default=sa.text("'stable'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_devices_update_channel"), "devices", "update_channel IN ('pilot', 'stable')"
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
