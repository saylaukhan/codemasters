"""``make api-pdf`` entry point: ``python -m app.openapi_pdf <openapi.json> <api.pdf>``.

Description of the API as one file of the delivery (plan.md §15, T-57): Swagger at ``/api/docs``
stays the live reference, the PDF is what goes into the folder of documents next to the
instructions. The source is the exported contract ``docs/reference/openapi.json`` (ADR-009) and
not the running application: the delivered PDF and the contract of the repository are then the
same file, and building it needs neither a database nor a server — only ``make openapi`` before.

Drawn by the generator of the school report (``app/services/exports/pdf.py``) with the page
cursor, the headings and the tables of ``report_pdf.py``, the way the PDF of an appeal is drawn
(``app/services/appeals/pdf.py``): A4, the embedded DejaVu Sans for the Cyrillic, the light
tokens of DESIGN.md. WeasyPrint of plan.md §2 is not among the dependencies.

What the contract does not carry is not invented here: the permission of ``require(...)`` lives
in ``app/auth/permissions.py`` and never reaches OpenAPI, so an operation shows the security
scheme it declares, not the permission code.
"""

import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.exports.pdf import PAGE_HEIGHT, PdfDocument
from app.services.exports.report_pdf import (
    BORDER,
    CONTENT_WIDTH,
    MARGIN,
    MUTED,
    SECONDARY,
    TEXT,
    Column,
    Layout,
    fit,
    wrap,
)

# One operation of the contract: its tag, method, path and body.
type Operation = tuple[str, str, str, dict[str, Any]]

# Methods of an OpenAPI path item, in the order they are printed.
METHODS = ("get", "post", "patch", "put", "delete")

# Captions of the sections: the contract has no top-level ``tags``, so the groups are named
# here by what their routers are (``backend/app/api/``), in Russian as the rest of the file.
TAG_CAPTIONS = {
    "health": "Проверка живости",
    "auth": "Вход в панель",
    "agent": "Агент на компьютере школы",
    "dashboard": "Сводка",
    "map": "Карта",
    "schools": "Школы, линии и точки мониторинга",
    "devices": "Устройства и коды установки",
    "analytics": "Аналитика",
    "incidents": "Инциденты",
    "appeals": "Обращения к поставщику",
    "notifications": "Уведомления",
    "exports": "Выгрузки",
    "admin": "Администрирование",
}

TYPE_NAMES = {
    "string": "строка",
    "integer": "целое",
    "number": "число",
    "boolean": "да/нет",
    "object": "объект",
    "null": "null",
}
FORMAT_NAMES = {
    "date-time": "дата и время",
    "date": "дата",
    "uuid": "uuid",
    "email": "e-mail",
    "binary": "файл",
}
PARAMETER_PLACES = {"path": "в пути", "query": "в строке запроса", "header": "заголовок"}

# The answer every operation has, described once in the overview instead of in 90 tables.
COMMON_RESPONSE = "default"
NO_VALUE = "—"

# Key of the section «Схемы» in the map of pages: it has no tag of the contract to be keyed by.
SCHEMAS_KEY = "__schemas__"

# How ``Layout.table`` draws a cell: size of its text and the padding it takes off the width of
# the column (3 on the left, 3 on the right). Repeated here because ``wrapped`` has to break a
# line exactly where ``fit`` would have cut it; ``report_pdf.py`` belongs to the exports.
TABLE_TEXT_SIZE = 7.5
TABLE_CELL_PADDING = 6.0


def ref_name(ref: str) -> str:
    """``#/components/schemas/Problem`` → ``Problem``."""
    return ref.rsplit("/", 1)[-1]


def plain(text: str) -> str:
    """A description as a line of prose: the Markdown marks of the contract dropped, as the PDF
    of an appeal drops them, and the line breaks of the docstring folded into spaces."""
    return " ".join(text.replace("**", "").replace("`", "").split())


def paragraphs(text: str) -> list[str]:
    """Paragraphs of a description: blank lines separate them, inside them lines join."""
    return [plain(block) for block in text.split("\n\n") if plain(block)]


def type_name(schema: dict[str, Any]) -> str:
    """Type of a value as the reference prints it: a schema name, a list, «строка или null»."""
    if "$ref" in schema:
        return ref_name(str(schema["$ref"]))
    if "anyOf" in schema:
        return " или ".join(type_name(variant) for variant in schema["anyOf"])
    if schema.get("type") == "array":
        items = schema.get("items")
        return f"массив {type_name(items)}" if isinstance(items, dict) else "массив"
    kind = schema.get("type")
    if isinstance(kind, str):
        name = TYPE_NAMES.get(kind, kind)
        fmt = schema.get("format")
        if isinstance(fmt, str):
            return f"{name} ({FORMAT_NAMES.get(fmt, fmt)})"
        return name
    return NO_VALUE


def security_line(operation: dict[str, Any], schemes: dict[str, Any]) -> str:
    """«Доступ: BearerAuth — Access-токен панели…», or that the operation is open."""
    names = [name for item in operation.get("security", []) for name in item]
    if not names:
        return "Доступ: без токена."
    parts = []
    for name in names:
        described = plain(str(schemes.get(name, {}).get("description", "")))
        parts.append(f"{name} — {described}" if described else name)
    return "Доступ: " + "; ".join(parts) + "."


def operations(contract: dict[str, Any]) -> list[Operation]:
    """``(tag, method, path, operation)`` of the contract, in the order of the paths."""
    found: list[Operation] = []
    for path, item in contract.get("paths", {}).items():
        for method in METHODS:
            operation = item.get(method)
            if isinstance(operation, dict):
                tags = operation.get("tags") or [NO_VALUE]
                found.append((str(tags[0]), method, str(path), operation))
    return found


def tag_order(found: Sequence[Operation]) -> list[str]:
    """Tags in the order the captions list them; an unknown tag goes last, by its name."""
    known = list(TAG_CAPTIONS)
    present = {tag for tag, _, _, _ in found}
    ordered = [tag for tag in known if tag in present]
    return ordered + sorted(present - set(ordered))


def wrapped(
    layout: Layout, columns: Sequence[Column], rows: Sequence[Sequence[str]], index: int
) -> list[list[str]]:
    """Rows for ``Layout.table`` in which the cell of ``index`` is broken into lines instead of
    being cut by ``fit`` with «…».

    Descriptions of the fields of a schema, of the parameters and of the answers are printed in
    this document only in these tables — a cut there loses the text for good, and the contract
    has enough prose for that to be a fifth of them. A description that does not fit continues
    on the rows under it, whose other columns stay empty.
    """
    width = columns[index].width - TABLE_CELL_PADDING
    out: list[list[str]] = []
    for row in rows:
        lines = wrap(layout.font, str(row[index]), width, TABLE_TEXT_SIZE)
        for number, line in enumerate(lines):
            cells = [str(cell) for cell in row] if number == 0 else [""] * len(row)
            cells[index] = line
            out.append(cells)
    return out


def break_page(layout: Layout) -> None:
    """Start the next page unless the current one is still empty."""
    if layout.y > MARGIN:
        layout.ensure(PAGE_HEIGHT)


def title_page(layout: Layout, contract: dict[str, Any], built_at: datetime) -> None:
    info = contract.get("info", {})
    layout.y += 60
    layout.text(MARGIN, layout.y, "Описание API", 9, SECONDARY)
    for line in wrap(layout.font, str(info.get("title", "")), CONTENT_WIDTH, 22):
        layout.y += 30
        layout.text(MARGIN, layout.y, line, 22, TEXT, bold=True)
    layout.y += 10
    version = f"Версия {info.get('version', NO_VALUE)} · OpenAPI {contract.get('openapi', '')}"
    layout.paragraph(version, 10, SECONDARY)
    layout.paragraph(f"Собрано {built_at:%d.%m.%Y} из docs/reference/openapi.json", 10, SECONDARY)
    layout.y += 10
    layout.page.line(MARGIN, layout.y, MARGIN + CONTENT_WIDTH, layout.y, BORDER)


def overview(layout: Layout, contract: dict[str, Any], found: Sequence[Operation]) -> None:
    layout.heading("Как читать этот документ", room=120)
    layout.paragraph(
        f"Разделов {len(tag_order(found))}, операций {len(found)}, схем "
        f"{len(contract.get('components', {}).get('schemas', {}))}. Документ собран из контракта "
        "OpenAPI — того же файла, по которому работает Swagger на /api/docs и из которого "
        "генерируется клиент панели (ADR-009). Разойтись они не могут: источник один."
    )
    layout.paragraph(
        "Ошибки все операции отдают одинаково — application/problem+json (RFC 9457, ADR-009). "
        f"Поэтому ответ «{COMMON_RESPONSE}» у каждой операции есть, но в таблицах ответов он не "
        "повторяется; его схема — Problem, у ошибки валидации — ValidationProblem."
    )
    layout.paragraph(
        "Право, которое проверяет require(...) на эндпоинте, в контракт не попадает — оно "
        "живёт в backend/app/auth/permissions.py. Здесь у операции указана схема доступа: "
        "каким токеном её вызывают."
    )
    schemes = contract.get("components", {}).get("securitySchemes", {})
    if schemes:
        layout.heading("Схемы доступа", room=80)
        layout.table(
            [Column("Схема", 110), Column("Где", 120), Column("Что это", 285.28)],
            [
                [
                    name,
                    f"{scheme.get('in', scheme.get('scheme', NO_VALUE))}"
                    f" {scheme.get('name', '')}".strip(),
                    plain(str(scheme.get("description", ""))) or NO_VALUE,
                ]
                for name, scheme in schemes.items()
            ],
        )


def contents(
    layout: Layout, contract: dict[str, Any], found: Sequence[Operation], pages: dict[str, int]
) -> None:
    """Sections with the page each starts on; the numbers come from the previous pass."""
    layout.heading("Разделы", room=120)
    rows = []
    for tag in tag_order(found):
        count = sum(1 for item in found if item[0] == tag)
        page = pages.get(tag)
        rows.append(
            [
                TAG_CAPTIONS.get(tag, tag),
                tag,
                str(count),
                str(page) if page else NO_VALUE,
            ]
        )
    schemas = contract.get("components", {}).get("schemas", {})
    if schemas:
        # «Схемы» takes about half of the document: it is a section of the contents like any
        # other, only keyed by ``SCHEMAS_KEY`` and counted in schemas instead of operations.
        page = pages.get(SCHEMAS_KEY)
        rows.append(["Схемы", NO_VALUE, str(len(schemas)), str(page) if page else NO_VALUE])
    layout.table(
        [
            Column("Раздел", 250),
            Column("Тег", 130),
            Column("Операций, или схем", 60, right=True),
            Column("Стр.", 75.28, right=True),
        ],
        rows,
    )


def responses_table(layout: Layout, operation: dict[str, Any]) -> None:
    rows = []
    for code, response in operation.get("responses", {}).items():
        if code == COMMON_RESPONSE:
            continue
        content = response.get("content", {})
        schema: dict[str, Any] = {}
        media = NO_VALUE
        for media_type, body in content.items():
            media = str(media_type)
            schema = body.get("schema", {})
            break
        rows.append(
            [
                str(code),
                plain(str(response.get("description", ""))) or NO_VALUE,
                type_name(schema) if schema else NO_VALUE,
                media,
            ]
        )
    if rows:
        columns = [
            Column("Код", 34, right=True),
            Column("Когда", 230),
            Column("Схема", 130),
            Column("Тип содержимого", 121.28),
        ]
        layout.table(columns, wrapped(layout, columns, rows, 1))


def parameters_table(layout: Layout, operation: dict[str, Any]) -> None:
    parameters = operation.get("parameters") or []
    if not parameters:
        return
    layout.paragraph("Параметры:", 8.5, SECONDARY)
    columns = [
        Column("Имя", 130),
        Column("Где", 90),
        Column("Тип", 130),
        Column("Обяз.", 45),
        Column("Что это", 120.28),
    ]
    rows = [
        [
            str(parameter.get("name", NO_VALUE)),
            PARAMETER_PLACES.get(str(parameter.get("in")), str(parameter.get("in"))),
            type_name(parameter.get("schema", {})),
            "да" if parameter.get("required") else "нет",
            plain(str(parameter.get("description", ""))) or NO_VALUE,
        ]
        for parameter in parameters
    ]
    layout.table(columns, wrapped(layout, columns, rows, 4))


def request_body(layout: Layout, operation: dict[str, Any]) -> None:
    body = operation.get("requestBody")
    if not isinstance(body, dict):
        return
    for media_type, content in body.get("content", {}).items():
        required = "обязательное" if body.get("required") else "необязательное"
        schema = type_name(content.get("schema", {}))
        layout.paragraph(f"Тело запроса: {schema} · {media_type} · {required}.", 8.5, SECONDARY)


def operation_block(
    layout: Layout, method: str, path: str, operation: dict[str, Any], schemes: dict[str, Any]
) -> None:
    layout.ensure(90)
    layout.y += 20
    layout.text(
        MARGIN,
        layout.y,
        fit(layout.font, f"{method.upper()}  {path}", CONTENT_WIDTH, 11),
        11,
        TEXT,
        bold=True,
    )
    summary = plain(str(operation.get("summary", "")))
    if summary:
        layout.paragraph(summary, 9.5, TEXT)
    layout.paragraph(security_line(operation, schemes), 8.5, MUTED)
    for block in paragraphs(str(operation.get("description", ""))):
        layout.paragraph(block, 8.5, SECONDARY)
    layout.y += 4
    parameters_table(layout, operation)
    request_body(layout, operation)
    layout.y += 4
    responses_table(layout, operation)


def tag_section(
    layout: Layout,
    tag: str,
    found: Sequence[Operation],
    schemes: dict[str, Any],
    pages: dict[str, int],
) -> None:
    mine = [item for item in found if item[0] == tag]
    break_page(layout)
    layout.heading(TAG_CAPTIONS.get(tag, tag), room=120)
    pages[tag] = len(layout.document.pages)
    layout.paragraph(f"Тег {tag}, операций {len(mine)}.", 8.5, MUTED)
    layout.y += 4
    columns = [Column("Метод", 55), Column("Путь", 250), Column("Что делает", 210.28)]
    rows = [
        [
            method.upper(),
            path,
            plain(str(operation.get("summary", ""))) or NO_VALUE,
        ]
        for _, method, path, operation in mine
    ]
    layout.table(columns, wrapped(layout, columns, rows, 2))
    for _, method, path, operation in mine:
        operation_block(layout, method, path, operation, schemes)


def schema_block(layout: Layout, name: str, schema: dict[str, Any]) -> None:
    layout.ensure(90)
    layout.y += 18
    layout.text(MARGIN, layout.y, name, 11, TEXT, bold=True)
    for block in paragraphs(str(schema.get("description", ""))):
        layout.paragraph(block, 8.5, SECONDARY)
    enum = schema.get("enum")
    if isinstance(enum, list):
        layout.paragraph("Значения: " + ", ".join(str(value) for value in enum), 8.5, TEXT)
        return
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        layout.paragraph("Без полей.", 8.5, MUTED)
        return
    required = set(schema.get("required", []))
    layout.y += 4
    columns = [
        Column("Поле", 140),
        Column("Тип", 160),
        Column("Обяз.", 45),
        Column("Что это", 170.28),
    ]
    rows = [
        [
            field,
            type_name(definition),
            "да" if field in required else "нет",
            plain(str(definition.get("description", ""))) or NO_VALUE,
        ]
        for field, definition in properties.items()
    ]
    layout.table(columns, wrapped(layout, columns, rows, 3))


def schemas_section(layout: Layout, contract: dict[str, Any], pages: dict[str, int]) -> None:
    schemas = contract.get("components", {}).get("schemas", {})
    if not schemas:
        return
    break_page(layout)
    layout.heading("Схемы", room=120)
    pages[SCHEMAS_KEY] = len(layout.document.pages)
    layout.paragraph(
        f"Все {len(schemas)} схем контракта по алфавиту: тела запросов, ответы и перечисления. "
        "Панель получает их же типами — web/src/api/generated (make openapi).",
        8.5,
        MUTED,
    )
    for name in sorted(schemas):
        schema_block(layout, name, schemas[name])


def footers(document: PdfDocument, contract: dict[str, Any]) -> None:
    font = document.font
    info = contract.get("info", {})
    name = f"{info.get('title', '')} · API {info.get('version', '')}"
    for number, page in enumerate(document.pages, start=1):
        y = PAGE_HEIGHT - 32
        page.line(MARGIN, y - 12, MARGIN + CONTENT_WIDTH, y - 12, BORDER)
        numbering = f"Стр. {number} из {len(document.pages)}"
        page.text(MARGIN, y, fit(font, name, 400, 7.5), size=7.5, color=MUTED)
        page.text(
            MARGIN + CONTENT_WIDTH - font.width(numbering, 7.5),
            y,
            numbering,
            size=7.5,
            color=MUTED,
        )


def draw(
    contract: dict[str, Any], pages: dict[str, int], built_at: datetime
) -> tuple[PdfDocument, dict[str, int]]:
    """Draw the whole document once; return it and the page each section started on."""
    info = contract.get("info", {})
    document = PdfDocument(f"{info.get('title', 'API')} — описание API")
    layout = Layout(document)
    found = operations(contract)
    schemes = contract.get("components", {}).get("securitySchemes", {})
    seen: dict[str, int] = {}
    title_page(layout, contract, built_at)
    overview(layout, contract, found)
    contents(layout, contract, found, pages)
    for tag in tag_order(found):
        tag_section(layout, tag, found, schemes, seen)
    schemas_section(layout, contract, seen)
    footers(document, contract)
    return document, seen


def build(contract: dict[str, Any], built_at: datetime | None = None) -> PdfDocument:
    """The contract as a document. Drawn twice: the first pass learns the page each section
    starts on, the second prints those numbers in «Разделы». The table of sections keeps its
    size between the passes — one row per tag plus one for «Схемы», whether the number is known
    or «—» — so the second pass lays out exactly like the first and the numbers it prints stay
    true."""
    moment = built_at or datetime.now()
    _, pages = draw(contract, {}, moment)
    document, _ = draw(contract, pages, moment)
    return document


def api_pdf(contract: dict[str, Any], built_at: datetime | None = None) -> bytes:
    """Bytes of the PDF of ``contract``."""
    return build(contract, built_at).to_bytes()


def export_pdf(source: Path, target: Path) -> int:
    """Read the contract of ``source``, write its PDF to ``target``, return the page count."""
    contract = json.loads(source.read_text(encoding="utf-8"))
    document = build(contract)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(document.to_bytes())
    return len(document.pages)


def main(argv: list[str]) -> int:
    """Parse the source and target paths from ``argv`` and write the PDF."""
    if len(argv) != 3:
        sys.stderr.write(
            "использование: python -m app.openapi_pdf <путь к openapi.json> <путь к api.pdf>\n"
        )
        return 2
    source, target = Path(argv[1]), Path(argv[2])
    if not source.is_file():
        sys.stderr.write(f"api-pdf: нет файла {source} — соберите контракт: make openapi\n")
        return 1
    pages = export_pdf(source, target)
    sys.stdout.write(f"api-pdf: {target}, страниц {pages}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
