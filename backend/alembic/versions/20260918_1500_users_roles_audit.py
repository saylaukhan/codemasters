"""Users of the panel: roles, users, user_scopes, audit_log (T-20, ADR-008).

The five roles of ТЗ п. 16 are rows of ``roles`` created here; what each may do is the
permission matrix in ``app/auth/permissions.py``. ``audit_log`` is append-only: a trigger
rejects UPDATE and DELETE, so the log of a blocked user stays (ТЗ п. 12, п. 16).

Revision ID: d4b8e21f6a90
Revises: c1a7d35b8e60
Create Date: 2026-09-18 15:00:12.504117+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4b8e21f6a90"
down_revision: str | None = "c1a7d35b8e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = {
    "school": "Школа",
    "district": "Район/город",
    "oblast": "Область",
    "provider": "Провайдер",
    "admin": "Администратор",
}

AUDIT_ACTIONS = (
    "login_success",
    "login_failure",
    "create",
    "update",
    "block",
    "unblock",
    "password_reset",
    "status_change",
    "export",
    "transfer_error",
)
AUDIT_ENTITY_TYPES = (
    "user",
    "school",
    "line",
    "school_contact",
    "device",
    "enrollment_code",
    "region",
    "provider",
    "connection_type",
    "threshold_profile",
    "schedule",
    "setting",
    "incident_rule",
    "agent_release",
    "incident",
    "appeal",
    "export",
)


def one_of(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
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
    ]


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_roles")),
    )
    op.bulk_insert(roles, [{"code": code, "name": name} for code, name in ROLES.items()])

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("token_version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["role"], ["roles.code"], name=op.f("fk_users_role_roles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "user_scopes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
        sa.Column("school_id", sa.BigInteger(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "num_nonnulls(region_id, provider_id, school_id) = 1",
            name=op.f("ck_user_scopes_one_scope"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name=op.f("fk_user_scopes_provider_id_providers")
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_user_scopes_region_id_regions")
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_user_scopes_school_id_schools")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_scopes_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_scopes")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_scopes_user_id")),
    )
    op.create_index(
        op.f("ix_user_scopes_provider_id"), "user_scopes", ["provider_id"], unique=False
    )
    op.create_index(op.f("ix_user_scopes_region_id"), "user_scopes", ["region_id"], unique=False)
    op.create_index(op.f("ix_user_scopes_school_id"), "user_scopes", ["school_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("user_email", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.CheckConstraint(one_of("action", AUDIT_ACTIONS), name=op.f("ck_audit_log_action")),
        sa.CheckConstraint(
            one_of("entity_type", AUDIT_ENTITY_TYPES), name=op.f("ck_audit_log_entity_type")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)

    # The log is never changed or deleted, not even by the application (ТЗ п. 16, ADR-008).
    op.execute(
        """
        CREATE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()"
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
