"""Source of a measurement: ``measurements.source`` (T-79; ТЗ п. 2, п. 9).

A measurement is taken by the schedule of the agent or by a press of «Замерить сейчас» in the
panel (ADR-016). Both are real measurements of the line and are kept side by side, but a row
must say which it is: an administrator reading the history of a computer sees why a measurement
stands outside the slots, and the aggregates keep the option of leaving the manual ones out
later without guessing by the clock.

Existing rows are measurements of the schedule — the panel could not ask for one until now — so
the column is filled with ``schedule`` and stays NOT NULL. An agent older than this revision
sends no source, and the schema of the request fills the same default (``app/schemas/agent.py``).

Revision ID: b8e3d7a12f64
Revises: a7f2c9d41b85
Create Date: 2026-09-22 20:10:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e3d7a12f64"
down_revision: str | None = "a7f2c9d41b85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "measurements",
        sa.Column("source", sa.Text(), server_default=sa.text("'schedule'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_measurements_source"), "measurements", "source IN ('schedule', 'manual')"
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
