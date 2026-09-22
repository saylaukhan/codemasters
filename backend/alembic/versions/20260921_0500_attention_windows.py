"""Windows of «Требуют внимания» as settings: inattention to an incident and to an appeal.

The main screen of T-60 lists an incident that has waited for a responsible person longer than
``attention_incident_unassigned_hours`` and an appeal the provider has not moved longer than
``attention_appeal_no_answer_hours`` (docs/design/README.md §4.1, §6.3). Neither window is a
constant of the code: ТЗ п. 11 and п. 20 put every such number into the admin panel (ADR-004).
24 and 48 hours are the values §4.1 describes, so a running installation sees no change.

Revision ID: b2f7c4a91d38
Revises: 9a1c5e7b3d08
Create Date: 2026-09-21 05:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f7c4a91d38"
down_revision: str | None = "9a1c5e7b3d08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "attention_incident_unassigned_hours",
            sa.BigInteger(),
            server_default=sa.text("24"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "attention_appeal_no_answer_hours",
            sa.BigInteger(),
            server_default=sa.text("48"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
