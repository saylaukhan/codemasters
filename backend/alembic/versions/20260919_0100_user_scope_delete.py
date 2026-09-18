"""DELETE on ``user_scopes`` for the panel role (T-38).

``vko_panel`` never deletes (T-20): the panel blocks and deactivates. A scope row is not history
but a setting of the user, and a user who becomes Область or Администратор must lose it — the
check ``one_scope`` forbids a row without an id. The user administration therefore deletes that
one row; ``users`` itself is still never deleted (ТЗ п. 16).

Revision ID: 8b1f4d6e2c37
Revises: 5e2a8c4b7d19
Create Date: 2026-09-19 01:00:00.000000+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b1f4d6e2c37"
down_revision: str | None = "5e2a8c4b7d19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT DELETE ON user_scopes TO vko_panel")


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
