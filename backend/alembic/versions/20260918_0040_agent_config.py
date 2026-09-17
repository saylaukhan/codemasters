"""Agent configuration: schedules, threshold profiles, agent releases, intervals (T-17).

An agent gets its schedule and thresholds from the server, never from its own code (ТЗ п. 11,
п. 20; ADR-004, ADR-012). The global schedule with the four default slots of «Решения по
умолчанию» and the global profile with the base thresholds of ТЗ п. 11 are created here and not
in ``make seed``: ``GET /api/agent/config`` must answer on any migrated database, seeded or not.
Both are changed in the admin panel afterwards (T-37).

Revision ID: a3f1c7d9e204
Revises: 12d8fd66ef0b
Create Date: 2026-09-18 00:40:11.512874+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f1c7d9e204"
down_revision: str | None = "12d8fd66ef0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Four slots of «Решения по умолчанию», local Asia/Almaty time (ТЗ п. 2, ADR-014).
DEFAULT_SLOTS = (
    '[{"start": "08:30:00", "end": "09:00:00"}, {"start": "11:00:00", "end": "11:30:00"}, '
    '{"start": "13:30:00", "end": "14:00:00"}, {"start": "16:00:00", "end": "16:30:00"}]'
)


def timestamps() -> list[sa.Column[sa.DateTime]]:
    """``created_at`` / ``updated_at`` of ``TimestampMixin``."""
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=True),
        sa.Column("school_id", sa.BigInteger(), nullable=True),
        sa.Column("slots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'Asia/Almaty'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "scope IN ('global', 'district', 'school')", name=op.f("ck_schedules_scope")
        ),
        sa.CheckConstraint(
            "(region_id IS NOT NULL) = (scope = 'district')",
            name=op.f("ck_schedules_district_target"),
        ),
        sa.CheckConstraint(
            "(school_id IS NOT NULL) = (scope = 'school')", name=op.f("ck_schedules_school_target")
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_schedules_region_id_regions")
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_schedules_school_id_schools")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedules")),
        sa.UniqueConstraint("region_id", name=op.f("uq_schedules_region_id")),
        sa.UniqueConstraint("school_id", name=op.f("uq_schedules_school_id")),
    )
    op.create_index(
        "uq_schedules_scope",
        "schedules",
        ["scope"],
        unique=True,
        postgresql_where=sa.text("scope = 'global'"),
    )
    op.create_table(
        "threshold_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=True),
        sa.Column("line_id", sa.BigInteger(), nullable=True),
        sa.Column("download_min_mbps", sa.Double(), nullable=False),
        sa.Column("upload_min_mbps", sa.Double(), nullable=False),
        sa.Column("ping_max_ms", sa.Double(), nullable=False),
        sa.Column("jitter_max_ms", sa.Double(), nullable=False),
        sa.Column("packet_loss_max_pct", sa.Double(), nullable=False),
        sa.Column("unstable_deviation_pct", sa.Double(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "scope IN ('global', 'district', 'line')", name=op.f("ck_threshold_profiles_scope")
        ),
        sa.CheckConstraint(
            "(region_id IS NOT NULL) = (scope = 'district')",
            name=op.f("ck_threshold_profiles_district_target"),
        ),
        sa.CheckConstraint(
            "(line_id IS NOT NULL) = (scope = 'line')",
            name=op.f("ck_threshold_profiles_line_target"),
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_threshold_profiles_region_id_regions")
        ),
        sa.ForeignKeyConstraint(
            ["line_id"], ["lines.id"], name=op.f("fk_threshold_profiles_line_id_lines")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_threshold_profiles")),
        sa.UniqueConstraint("region_id", name=op.f("uq_threshold_profiles_region_id")),
        sa.UniqueConstraint("line_id", name=op.f("uq_threshold_profiles_line_id")),
    )
    op.create_index(
        "uq_threshold_profiles_scope",
        "threshold_profiles",
        ["scope"],
        unique=True,
        postgresql_where=sa.text("scope = 'global'"),
    )
    op.create_table(
        "agent_releases",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("download_url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint(
            "channel IN ('pilot', 'stable')", name=op.f("ck_agent_releases_channel")
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_agent_releases_sha256")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_releases")),
        sa.UniqueConstraint("version", name=op.f("uq_agent_releases_version")),
    )
    op.create_index(
        "ix_agent_releases_channel_released_at",
        "agent_releases",
        ["channel", "released_at"],
        unique=False,
    )

    # Intervals of the agent live in the settings, not in its code (ТЗ п. 20, ADR-012).
    op.add_column(
        "settings",
        sa.Column(
            "heartbeat_interval_s", sa.BigInteger(), server_default=sa.text("300"), nullable=False
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "config_refresh_interval_s",
            sa.BigInteger(),
            server_default=sa.text("900"),
            nullable=False,
        ),
    )

    # The two rows every agent configuration falls back to; the admin panel changes them (T-37).
    op.execute(f"INSERT INTO schedules (scope, slots) VALUES ('global', '{DEFAULT_SLOTS}'::jsonb)")
    op.execute(
        "INSERT INTO threshold_profiles (scope, download_min_mbps, upload_min_mbps, ping_max_ms, "
        "jitter_max_ms, packet_loss_max_pct, unstable_deviation_pct) "
        "VALUES ('global', 20, 20, 100, 30, 2, 30)"
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
