"""Appeals to providers (ТЗ п. 17, plan.md §8, ADR-011): facts, prompt, draft, sending.

The facts of an appeal are collected by ``context.py``, the prompt built from them by
``prompt.py``, and the draft the editor of T-47 opens with by ``draft.py``. «Отправить» is
``send.py``: the number ``ОБР-2026-000045``, the PDF of ``pdf.py`` and the letter to the
provider. What happens to a sent appeal afterwards — the list, the card, the status and the
history — is ``card.py`` (T-48).
"""

from app.services.appeals.card import (
    AppealFilters,
    appeal_detail,
    appeal_list,
    appeal_pdf_file,
    update_appeal,
)
from app.services.appeals.context import appeal_facts
from app.services.appeals.draft import appeal_draft
from app.services.appeals.send import create_appeal

__all__ = [
    "AppealFilters",
    "appeal_detail",
    "appeal_draft",
    "appeal_facts",
    "appeal_list",
    "appeal_pdf_file",
    "create_appeal",
    "update_appeal",
]
