"""Queue retention of an agent as a setting: ``settings.agent_queue_retention_days``.

How long an agent keeps a measurement in its queue, and how far back the server accepts one,
was a constant in the code on both sides (``MAX_QUEUE_AGE`` of the schemas, ``MaxAge`` of the
agent). ТЗ п. 11 and п. 20 allow no such constant: the value belongs to the admin panel and
reaches the agent with ``GET /api/agent/config`` (ADR-004, ADR-006, ADR-012). 30 days is what
both constants held, so nothing changes for an installation that is already running.

Revision ID: 9a1c5e7b3d08
Revises: 6d3f8a1c9b42
Create Date: 2026-09-21 03:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a1c5e7b3d08"
down_revision: str | None = "6d3f8a1c9b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "agent_queue_retention_days",
            sa.BigInteger(),
            server_default=sa.text("30"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_settings_agent_queue_retention_days"),
        "settings",
        "agent_queue_retention_days BETWEEN 1 AND 365",
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
