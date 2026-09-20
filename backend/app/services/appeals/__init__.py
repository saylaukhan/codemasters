"""Appeals to providers (ТЗ п. 17, plan.md §8, ADR-011): facts, prompt, draft.

The facts of an appeal are collected by ``context.py``, the prompt built from them by
``prompt.py``, and the draft the editor of T-47 opens with by ``draft.py``. The sending, the
number ``ОБР-2026-000045``, the letter to the provider, the PDF and the history are T-48.
"""

from app.services.appeals.context import appeal_facts
from app.services.appeals.draft import appeal_draft

__all__ = ["appeal_draft", "appeal_facts"]
