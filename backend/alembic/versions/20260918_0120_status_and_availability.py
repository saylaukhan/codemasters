"""School status and availability: settings of the status rules, idempotent outages (T-16).

Nothing of the rules lives in code: how long silence means «Нет соединения», how many
measurements decide the status of a school, the working hours downtime is counted inside and
the availability target of ТЗ п. 11 are columns of ``settings`` (ADR-004, ADR-014). The unique
index on ``outages`` makes a resent outage a 409 instead of a second row (ADR-006).

Revision ID: 7c41b0ad5e93
Revises: a3f1c7d9e204
Create Date: 2026-09-18 01:20:44.118907+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7c41b0ad5e93"
down_revision: str | None = "a3f1c7d9e204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Working hours of «Решения по умолчанию» and ADR-014: 08:00–18:00, Mon–Sat, local time.
DEFAULT_WORKING_HOURS = (
    '{"weekdays": ["mon", "tue", "wed", "thu", "fri", "sat"], '
    '"start": "08:00:00", "end": "18:00:00"}'
)


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("timezone", sa.Text(), server_default=sa.text("'Asia/Almaty'"), nullable=False),
    )
    op.add_column(
        "settings",
        sa.Column(
            "offline_after_s", sa.BigInteger(), server_default=sa.text("900"), nullable=False
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "school_status_measurements_count",
            sa.BigInteger(),
            server_default=sa.text("3"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "default_working_hours",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(f"'{DEFAULT_WORKING_HOURS}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "availability_min_pct", sa.Double(), server_default=sa.text("99"), nullable=False
        ),
    )

    # Idempotency of a resent outage: the device comes from the token, so the key is the pair
    # (device, started_at) (ADR-006). It starts with device_id, so it also covers the foreign
    # key, and the plain index created with the table in T-02 becomes a duplicate.
    op.create_index(
        "uq_outages_device_id_started_at", "outages", ["device_id", "started_at"], unique=True
    )
    op.drop_index("ix_outages_device_id_started_at", table_name="outages")


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
