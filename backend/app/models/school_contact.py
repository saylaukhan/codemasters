"""``school_contacts``: people responsible at a school (ТЗ п. 15).

The only table with personal data (ADR-003); none of it is ever sent to an LLM (ADR-011).
"""

from sqlalchemy import ForeignKey, Identity
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SchoolContact(TimestampMixin, Base):
    """Responsible person of a school and the provider support contact for that school."""

    __tablename__ = "school_contacts"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    full_name: Mapped[str]
    position: Mapped[str | None]
    phone: Mapped[str | None]
    email: Mapped[str | None]
    provider_support_contact: Mapped[str | None]
