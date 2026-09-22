"""Measurement asked for from the panel: ``devices.measure_requested_at`` (T-79; ТЗ п. 2, п. 12).

The agent connects outwards only (ADR-006), so a measurement «on command» is a mark the panel
leaves on the row: the agent sees the moment of the request in the answer of
``POST /api/devices/heartbeat``, measures once outside its schedule and sends the result the
usual way. The column holds that moment and nothing else: the measurement itself is an ordinary
row of ``measurements`` (ADR-004), and the schedule of the device does not change (ТЗ п. 2).

The mark is cleared by the measurement that answers it; a request the agent never took — the
computer was off — simply grows older than ``MEASURE_REQUEST_TTL`` of
``app/schemas/agent.py`` and stops being handed out.

Revision ID: a7f2c9d41b85
Revises: c3d9f1a7b6e4
Create Date: 2026-09-22 16:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7f2c9d41b85"
down_revision: str | None = "c3d9f1a7b6e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices", sa.Column("measure_requested_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
