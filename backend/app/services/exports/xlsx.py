"""The smallest valid XLSX of one sheet: a bold frozen header with a filter, then the rows.

An XLSX is a ZIP of SpreadsheetML parts (ECMA-376); strings go inline, numbers as numbers, so
Excel and LibreOffice sort and sum them. Written with the standard library: openpyxl of
plan.md §2 is not among the dependencies yet (docs/known-limitations.md, T-30).
"""

import math
import re
import zipfile
from collections.abc import Iterable, Sequence
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

type Cell = str | int | float | None

# Characters XML 1.0 forbids; a hostname or a server name must not break the file.
INVALID_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
# Excel limits a sheet name to 31 characters and forbids these.
INVALID_SHEET_NAME = re.compile(r"[\[\]:*?/\\]")

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""  # noqa: E501

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""  # noqa: E501

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""  # noqa: E501

WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name={name} sheetId="1" r:id="rId1"/></sheets>
</workbook>"""  # noqa: E501

# Style 0 — the default, style 1 — the bold header.
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""  # noqa: E501


def column_letter(index: int) -> str:
    """Letters of the 0-based column: 0 → A, 25 → Z, 26 → AA."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def cell_xml(reference: str, value: Cell, style: int = 0) -> str:
    styled = f' s="{style}"' if style else ""
    if value is None:
        return ""
    if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value):
        return f'<c r="{reference}"{styled}><v>{value!r}</v></c>'
    text = escape(INVALID_XML.sub("", str(value)))
    inline = f'<is><t xml:space="preserve">{text}</t></is>'
    return f'<c r="{reference}"{styled} t="inlineStr">{inline}</c>'


def sheet_xml(header: Sequence[str], rows: Iterable[Sequence[Cell]]) -> str:
    letters = [column_letter(index) for index in range(len(header))]
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>",
        "<cols>",
        *(
            f'<col min="{index}" max="{index}" width="{max(10, len(title) + 4)}" customWidth="1"/>'
            for index, title in enumerate(header, start=1)
        ),
        "</cols><sheetData>",
        '<row r="1">',
        *(
            cell_xml(f"{letter}1", title, style=1)
            for letter, title in zip(letters, header, strict=True)
        ),
        "</row>",
    ]
    last_row = 1
    for number, row in enumerate(rows, start=2):
        last_row = number
        parts.append(f'<row r="{number}">')
        parts.extend(
            cell_xml(f"{letter}{number}", value) for letter, value in zip(letters, row, strict=True)
        )
        parts.append("</row>")
    parts.append("</sheetData>")
    if letters:
        parts.append(f'<autoFilter ref="A1:{letters[-1]}{last_row}"/>')
    parts.append("</worksheet>")
    return "".join(parts)


def xlsx_bytes(sheet_name: str, header: Sequence[str], rows: Iterable[Sequence[Cell]]) -> bytes:
    """XLSX file with one sheet: ``header`` in bold, frozen and filtered, then ``rows``."""
    name = INVALID_SHEET_NAME.sub(" ", sheet_name)[:31] or "Лист1"
    sheet = sheet_xml(header, rows)
    workbook = WORKBOOK.format(name=quoteattr(name))
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", ROOT_RELS)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        archive.writestr("xl/styles.xml", STYLES)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
