"""Weights and the passing threshold of the provider score as settings (T-68, ТЗ п. 14).

The score of a provider is 100 minus the penalties of its parts — measurements below the
contract, availability, reaction to an incident, incidents per school — and neither the weight
of a part nor the threshold «ниже нормы» is a constant of the code: ТЗ п. 11 and п. 20 put
every such number into the admin panel (ADR-004, docs/design/README.md §6.3). The defaults are
the numbers §6.3 describes — the threshold 70 and the reaction norm of 4 hours — so a running
installation sees the screen §6.3 draws. The four weights add up to 100, so an installation
that changes one of them keeps the score inside 0–100 by changing another.

Revision ID: a4e2c7b90d13
Revises: c3d9f1a7b6e4
Create Date: 2026-09-22 17:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4e2c7b90d13"
down_revision: str | None = "c3d9f1a7b6e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WEIGHTS = {
    "provider_score_weight_below_contract": "40",
    "provider_score_weight_availability": "20",
    "provider_score_weight_reaction": "25",
    "provider_score_weight_incidents": "15",
}


def upgrade() -> None:
    for name, default in WEIGHTS.items():
        op.add_column(
            "settings",
            sa.Column(name, sa.Double(), server_default=sa.text(default), nullable=False),
        )
    op.add_column(
        "settings",
        sa.Column(
            "provider_score_pass_pct", sa.Double(), server_default=sa.text("70"), nullable=False
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "provider_score_reaction_norm_hours",
            sa.Double(),
            server_default=sa.text("4"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
