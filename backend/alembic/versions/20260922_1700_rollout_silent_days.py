"""Window of «молчит» of the rollout screen as a setting: days without a heartbeat.

«Внедрение» of T-69 lists a school whose agent is installed but has not been heard for longer
than ``rollout_silent_days`` (docs/design/README.md §6.4). The window is not a constant of the
code: ТЗ п. 11 and п. 20 put every such number into the admin panel (ADR-004). 7 days is the
value §6.4 describes, so a running installation sees no change.

Revision ID: f1a6d24b9c83
Revises: c3d9f1a7b6e4
Create Date: 2026-09-22 17:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a6d24b9c83"
down_revision: str | None = "c3d9f1a7b6e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "rollout_silent_days", sa.BigInteger(), server_default=sa.text("7"), nullable=False
        ),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
