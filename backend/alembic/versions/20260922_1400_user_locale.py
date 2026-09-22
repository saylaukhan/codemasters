"""Language of the panel of a user: ``users.locale`` (T-66; DESIGN.md §5.1).

The panel is Russian and Kazakh (ADR-010, no i18n framework): the choice lives in the browser
of the person and in his profile, so a new browser opens the panel in the language he picked
and the letters and PDF summaries of T-67 have a language to be written in. Existing accounts
keep the language the panel has had until now — Russian.

Revision ID: e7a4c2b81f36
Revises: d5b9a3c71e42
Create Date: 2026-09-22 14:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a4c2b81f36"
down_revision: str | None = "d5b9a3c71e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.Text(), server_default=sa.text("'ru'"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_users_locale"), "users", "locale IN ('ru', 'kk')")


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
