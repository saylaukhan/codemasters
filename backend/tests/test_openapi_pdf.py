"""PDF of the contract for the delivery (plan.md §15, T-57): ``app/openapi_pdf.py``.

The generator draws with the cursor and the tables of ``app/services/exports/report_pdf.py``,
which belongs to the exports and changes for their reasons. Nothing else runs this module —
``make api-pdf`` is not part of ``make check`` and the PDF it writes is not in the repository —
so these tests are what notices when ``Layout``, ``Column`` or ``fit`` move under it.

Two of them guard a defect the generator already had: the section «Схемы», half of the
document, was missing from the contents, and a description longer than its column was cut with
«…» although it is printed nowhere else.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.openapi_pdf import SCHEMAS_KEY, api_pdf, build, draw
from tests.test_exports_report import pdf_text

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "reference" / "openapi.json"

# A description longer than the column «Что это» of the table of fields (170.28 minus padding).
LONG_DESCRIPTION = (
    "Администратор запросил новый токен: агент вызывает POST /api/agent/token текущим токеном "
    "и дальше живёт с полученным, старый перестаёт действовать сразу после обмена."
)


def contract() -> dict[str, Any]:
    """A contract of one operation and one schema — enough for every part of the document."""
    return {
        "openapi": "3.1.0",
        "info": {"title": "Мониторинг интернета ВКО", "version": "1.0.0"},
        "paths": {
            "/api/agent/config": {
                "get": {
                    "tags": ["agent"],
                    "summary": "Настройки агента: пороги, расписание и адреса серверов замеров",
                    "parameters": [
                        {
                            "name": "since",
                            "in": "query",
                            "schema": {"type": "string", "format": "date-time"},
                            "description": LONG_DESCRIPTION,
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": LONG_DESCRIPTION,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/AgentConfigResponse"}
                                }
                            },
                        },
                        "default": {"description": "Ошибка"},
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "AgentConfigResponse": {
                    "type": "object",
                    "required": ["token_rotation_required"],
                    "properties": {
                        "token_rotation_required": {
                            "type": "boolean",
                            "description": LONG_DESCRIPTION,
                        }
                    },
                }
            }
        },
    }


def test_the_contents_names_the_schemas_and_the_page_they_start_on() -> None:
    """«Схемы» is a section of the contents like any tag: its page was computed and dropped."""
    body = contract()
    _, pages = draw(body, {}, datetime(2026, 9, 21))
    assert SCHEMAS_KEY in pages

    text = pdf_text(api_pdf(body, datetime(2026, 9, 21)))
    lines = text.splitlines()
    # The caption of the contents, the row of the only tag, then the row of the schemas.
    assert "Разделы" in lines
    assert "Агент на компьютере школы" in lines
    assert "Схемы" in lines
    # The page of the row is the page the section really starts on.
    assert str(pages[SCHEMAS_KEY]) in lines


def test_a_description_longer_than_its_column_stays_whole() -> None:
    """A field, a parameter and an answer keep their text: the tables wrap instead of cutting."""
    text = pdf_text(api_pdf(contract(), datetime(2026, 9, 21)))
    joined = " ".join(text.splitlines())
    assert LONG_DESCRIPTION in joined
    # «…» of ``fit`` means a cut cell, and the cut text is in no other place of the document.
    assert "…" not in text


def test_the_second_pass_prints_the_page_numbers_of_the_first() -> None:
    """The contents may not move the sections it numbers, or the numbers it prints are wrong."""
    body, moment = contract(), datetime(2026, 9, 21)
    _, first = draw(body, {}, moment)
    _, second = draw(body, first, moment)
    assert first == second


def test_the_contract_of_the_repository_builds() -> None:
    """The real ``docs/reference/openapi.json``: every path of it is drawn without an exception."""
    body = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    document = build(body, datetime(2026, 9, 21))
    data = document.to_bytes()
    assert data.startswith(b"%PDF-")
    assert len(document.pages) > 1
    # The trailing space tells a page from the ``/Type /Pages`` of the tree that holds them.
    assert data.count(b"/Type /Page ") == len(document.pages)
