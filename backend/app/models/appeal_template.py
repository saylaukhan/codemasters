"""``appeal_templates``: the letters to providers the model writes by (T-60; ТЗ п. 17, п. 20).

A template is the subject and the body of the letter with placeholders — ``{{school_name}}``,
``{{contract_number}}``, ``{{metrics}}`` — the server fills with the facts of the appeal
(``app/services/appeals/template.py``), and the instructions the model gets on top of them.
The filled template is what the model is asked to write from, and what the editor opens with
when the model is silent (ADR-011). Two kinds: an ordinary appeal and a formal claim, which the
list, the card and the PDF of a sent appeal name.

Exactly one template is the default — the one the draft takes without a choice; a partial
unique index holds that. A template is switched off with ``is_active``, never deleted: the
appeals written by it refer to it.
"""

from sqlalchemy import CheckConstraint, Identity, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base, TimestampMixin

# Codes of ``AppealKind`` in ``app/schemas/appeal_templates.py``.
KINDS = ("appeal", "claim")


class AppealTemplate(TimestampMixin, Base):
    """One template: what the letter is called, what it says and how the model must write it."""

    __tablename__ = "appeal_templates"
    __table_args__ = (
        CheckConstraint(one_of("kind", KINDS), name="kind"),
        Index(
            "uq_appeal_templates_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    # Subject and body of the letter with placeholders; Markdown in the body (ADR-011).
    subject: Mapped[str]
    body: Mapped[str]
    # What the model is told on top of the facts and the filled template; not rendered.
    ai_instructions: Mapped[str | None]
    is_default: Mapped[bool] = mapped_column(server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
