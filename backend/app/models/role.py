"""``roles``: the five roles of ТЗ п. 16 (ADR-008).

The set is fixed and created by the migration; what a role may do is the permission matrix in
``app/auth/permissions.py``, not a column: a change of rights is a change of code with a test.
"""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Role(TimestampMixin, Base):
    """Role of a panel user; ``code`` is the ``UserRole`` of the API."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
