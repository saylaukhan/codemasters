"""Schema v1: reference data, schools, lines, points, devices, measurements, heartbeats (T-02).

Tables and fields follow plan.md §5 and ADR-003. ``measurements`` and ``heartbeats`` are
TimescaleDB hypertables; geometry of ``regions`` and ``schools`` is PostGIS in WGS 84. Row-level
security on tables with a visibility scope arrives with ``app.user_scope`` in T-20 (ADR-008).

Revision ID: 72bc0e369aa3
Revises:
Create Date: 2026-09-17 00:06:44.983424+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "72bc0e369aa3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "connection_types",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connection_types")),
        sa.UniqueConstraint("code", name=op.f("uq_connection_types_code")),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_providers")),
        sa.UniqueConstraint("name", name=op.f("uq_providers_name")),
    )
    op.create_table(
        "regions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "geom",
            Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regions")),
        sa.UniqueConstraint("code", name=op.f("uq_regions_code")),
    )
    op.create_index("ix_regions_geom", "regions", ["geom"], unique=False, postgresql_using="gist")
    op.create_table(
        "schools",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("school_code", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "geom",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_schools_region_id_regions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schools")),
        sa.UniqueConstraint("school_code", name=op.f("uq_schools_school_code")),
    )
    op.create_index("ix_schools_geom", "schools", ["geom"], unique=False, postgresql_using="gist")
    op.create_index(op.f("ix_schools_region_id"), "schools", ["region_id"], unique=False)
    op.create_table(
        "enrollment_codes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_enrollment_codes_school_id_schools")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollment_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_enrollment_codes_code_hash")),
    )
    op.create_index(
        op.f("ix_enrollment_codes_school_id"), "enrollment_codes", ["school_id"], unique=False
    )
    op.create_table(
        "lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("connection_type_id", sa.BigInteger(), nullable=True),
        sa.Column("line_identifier", sa.Text(), nullable=True),
        sa.Column("contract_down_mbps", sa.Double(), nullable=True),
        sa.Column("contract_up_mbps", sa.Double(), nullable=True),
        sa.Column("contract_number", sa.Text(), nullable=True),
        sa.Column("contract_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "ip_ranges",
            postgresql.ARRAY(postgresql.CIDR()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('main', 'reserve', 'disabled')", name=op.f("ck_lines_status")
        ),
        sa.ForeignKeyConstraint(
            ["connection_type_id"],
            ["connection_types.id"],
            name=op.f("fk_lines_connection_type_id_connection_types"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name=op.f("fk_lines_provider_id_providers")
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_lines_school_id_schools")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lines")),
        sa.UniqueConstraint("id", "school_id", name=op.f("uq_lines_id_school_id")),
    )
    op.create_index(
        op.f("ix_lines_connection_type_id"), "lines", ["connection_type_id"], unique=False
    )
    op.create_index(op.f("ix_lines_provider_id"), "lines", ["provider_id"], unique=False)
    op.create_index(op.f("ix_lines_school_id"), "lines", ["school_id"], unique=False)
    op.create_table(
        "school_contacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("provider_support_contact", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_school_contacts_school_id_schools")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_school_contacts")),
    )
    op.create_index(
        op.f("ix_school_contacts_school_id"), "school_contacts", ["school_id"], unique=False
    )
    op.create_table(
        "monitoring_points",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("line_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("room", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["line_id", "school_id"],
            ["lines.id", "lines.school_id"],
            name=op.f("fk_monitoring_points_line_id_school_id_lines"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitoring_points")),
    )
    op.create_index(
        "ix_monitoring_points_line_id_school_id",
        "monitoring_points",
        ["line_id", "school_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_monitoring_points_school_id"), "monitoring_points", ["school_id"], unique=False
    )
    op.create_index(
        "uq_monitoring_points_school_id_is_primary",
        "monitoring_points",
        ["school_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("device_uid", sa.Text(), nullable=False),
        sa.Column("monitoring_point_id", sa.BigInteger(), nullable=False),
        sa.Column("hostname", sa.Text(), nullable=True),
        sa.Column("os", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.Text(), nullable=True),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active', 'blocked')", name=op.f("ck_devices_status")),
        sa.ForeignKeyConstraint(
            ["monitoring_point_id"],
            ["monitoring_points.id"],
            name=op.f("fk_devices_monitoring_point_id_monitoring_points"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("device_uid", name=op.f("uq_devices_device_uid")),
    )
    op.create_index(
        op.f("ix_devices_monitoring_point_id"), "devices", ["monitoring_point_id"], unique=False
    )
    op.create_table(
        "heartbeats",
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("online", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_heartbeats_device_id_devices")
        ),
        sa.PrimaryKeyConstraint("device_id", "ts", name=op.f("pk_heartbeats")),
    )
    op.create_table(
        "measurements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("measurement_uuid", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("line_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("download_mbps", sa.Double(), nullable=True),
        sa.Column("upload_mbps", sa.Double(), nullable=True),
        sa.Column("ping_ms", sa.Double(), nullable=True),
        sa.Column("jitter_ms", sa.Double(), nullable=True),
        sa.Column("packet_loss_pct", sa.Double(), nullable=True),
        sa.Column("connection_status", sa.Text(), nullable=False),
        sa.Column("duration_s", sa.Double(), nullable=True),
        sa.Column("external_ip", postgresql.INET(), nullable=True),
        sa.Column("server", sa.Text(), nullable=True),
        sa.Column("iface_type", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.Text(), nullable=True),
        sa.Column("thresholds_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quality_status", sa.Text(), nullable=True),
        sa.Column("contract_ok", sa.Boolean(), nullable=True),
        sa.CheckConstraint(
            "connection_status IN ('online', 'offline')",
            name=op.f("ck_measurements_connection_status"),
        ),
        sa.CheckConstraint(
            "quality_status IN ('normal', 'unstable', 'critical', 'offline')",
            name=op.f("ck_measurements_quality_status"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_measurements_device_id_devices")
        ),
        sa.ForeignKeyConstraint(
            ["line_id"], ["lines.id"], name=op.f("fk_measurements_line_id_lines")
        ),
        sa.PrimaryKeyConstraint("id", "measured_at", name=op.f("pk_measurements")),
    )
    op.create_index(
        "ix_measurements_device_id_measured_at",
        "measurements",
        ["device_id", "measured_at"],
        unique=False,
    )
    op.create_index(
        "ix_measurements_line_id_measured_at",
        "measurements",
        ["line_id", "measured_at"],
        unique=False,
    )
    op.create_index("ix_measurements_measured_at", "measurements", ["measured_at"], unique=False)
    op.create_index(
        "uq_measurements_measurement_uuid",
        "measurements",
        ["measurement_uuid", "measured_at"],
        unique=True,
    )
    op.create_table(
        "outages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("line_id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name=op.f("ck_outages_period")
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_outages_device_id_devices")
        ),
        sa.ForeignKeyConstraint(["line_id"], ["lines.id"], name=op.f("fk_outages_line_id_lines")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outages")),
    )
    op.create_index(
        "ix_outages_device_id_started_at", "outages", ["device_id", "started_at"], unique=False
    )
    op.create_index(
        "ix_outages_line_id_started_at", "outages", ["line_id", "started_at"], unique=False
    )

    # Time series (ADR-003). Default hypertable indexes are off: every index these tables need is
    # declared in app.models and created above, so later autogenerate runs see no foreign indexes.
    op.execute(
        "SELECT create_hypertable('measurements', by_range('measured_at'), "
        "create_default_indexes => false)"
    )
    op.execute(
        "SELECT create_hypertable('heartbeats', by_range('ts'), create_default_indexes => false)"
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
