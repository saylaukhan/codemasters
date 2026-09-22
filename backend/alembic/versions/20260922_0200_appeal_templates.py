"""Templates of the letters to providers and the kind of an appeal (T-60; ТЗ п. 17; ADR-011).

``appeal_templates`` holds the letters the model writes by: the subject and the body with
placeholders such as ``{{school_name}}`` that the server fills with the facts of the appeal,
and the instructions the model gets on top of them. Until now the structure of the letter was a
constant of the code (``app/services/appeals/prompt.py``); ТЗ п. 20 wants it changed in the
admin panel like the thresholds. Two templates come with the migration: the appeal, which is
the default and repeats the letter of T-47, and the formal claim, which cites the contract and
demands a recalculation. Exactly one template is the default — a partial unique index holds
that; a template is switched off with ``is_active``, never deleted.

``appeals`` learns which template a letter was written by and its kind: an appeal or a claim
(``kind``), so the list, the card and the PDF name it. The audit log accepts
``appeal_template`` as an entity type.

Revision ID: 6c2f8d4e9b71
Revises: 3e7b9c1d5a24
Create Date: 2026-09-22 02:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6c2f8d4e9b71"
down_revision: str | None = "3e7b9c1d5a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'appeal', 'claim'"

AUDIT_ENTITY_TYPES = (
    "user",
    "school",
    "line",
    "monitoring_point",
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
    "appeal_template",
    "export",
)

APPEAL_SUBJECT = "{{topic}}: {{school_code}}, {{school_name}}, период {{period_dates}}"
APPEAL_BODY = """**{{provider_name}}**

Уважаемые коллеги!

По данным мониторинга качества интернет-соединения:

{{facts}}

Показатели за период:

{{metrics}}

Просим устранить нарушение качества услуги и сообщить о принятых мерах в срок, \
установленный договором."""
APPEAL_INSTRUCTIONS = (
    "Изложи факты деловым языком, сохрани все цифры, реквизиты и структуру шаблона."
)

CLAIM_SUBJECT = (
    "Претензия по договору {{contract_number}}: {{school_code}}, {{school_name}}, "
    "период {{period_dates}}"
)
CLAIM_BODY = """**{{provider_name}}**

ПРЕТЕНЗИЯ

по договору № {{contract_number}} от {{contract_date}} об оказании услуг доступа к сети \
Интернет для {{school_name}} (School ID {{school_code}}, линия {{line_identifier}}).

Согласно договору исполнитель обязан обеспечивать скорость доступа не ниже \
{{contract_down_mbps}} Мбит/с на приём и {{contract_up_mbps}} Мбит/с на передачу. По данным \
автоматического мониторинга за период {{period}}:

{{facts}}

Показатели за период:

{{metrics}}

Изложенное свидетельствует о нарушении условий договора. Требуем:

1. Устранить нарушение и обеспечить параметры услуги, установленные договором.
2. Произвести перерасчёт стоимости услуги за период ненадлежащего оказания.
3. Направить письменный ответ о принятых мерах в срок, установленный договором.

При неудовлетворении требований оставляем за собой право обратиться в уполномоченные органы \
и в суд в порядке, предусмотренном законодательством Республики Казахстан."""
CLAIM_INSTRUCTIONS = (
    "Официальный претензионный стиль со ссылками на договор, без эмоций; сохрани требования, "
    "цифры и реквизиты шаблона."
)

# name, kind, subject, body, instructions, is_default
DEFAULT_TEMPLATES = (
    ("Обращение поставщику", "appeal", APPEAL_SUBJECT, APPEAL_BODY, APPEAL_INSTRUCTIONS, True),
    ("Претензионное письмо", "claim", CLAIM_SUBJECT, CLAIM_BODY, CLAIM_INSTRUCTIONS, False),
)


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
    op.create_table(
        "appeal_templates",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("ai_instructions", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_appeal_templates_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeal_templates")),
    )
    # One default template: the rows with the flag collide on it.
    op.create_index(
        "uq_appeal_templates_default",
        "appeal_templates",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )

    op.add_column(
        "appeals",
        sa.Column("kind", sa.Text(), server_default=sa.text("'appeal'"), nullable=False),
    )
    op.add_column("appeals", sa.Column("template_id", sa.BigInteger(), nullable=True))
    op.create_check_constraint(op.f("ck_appeals_kind"), "appeals", f"kind IN ({KINDS})")
    op.create_foreign_key(
        op.f("fk_appeals_template_id_appeal_templates"),
        "appeals",
        "appeal_templates",
        ["template_id"],
        ["id"],
    )
    op.create_index(op.f("ix_appeals_template_id"), "appeals", ["template_id"])

    op.drop_constraint(op.f("ck_audit_log_entity_type"), "audit_log", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_log_entity_type"),
        "audit_log",
        f"entity_type IN ({', '.join(repr(value) for value in AUDIT_ENTITY_TYPES)})",
    )

    for name, kind, subject, body, instructions, is_default in DEFAULT_TEMPLATES:
        op.execute(
            sa.text(
                "INSERT INTO appeal_templates "
                "(name, kind, subject, body, ai_instructions, is_default) "
                "VALUES (:name, :kind, :subject, :body, :instructions, :is_default)"
            ).bindparams(
                name=name,
                kind=kind,
                subject=subject,
                body=body,
                instructions=instructions,
                is_default=is_default,
            )
        )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
