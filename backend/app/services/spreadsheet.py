"""Rows of a CSV or XLSX file as strings (T-61): the table an import reads.

CSV is read as Excel of the Russian locale writes it and as ``app/services/exports/files.py``
writes it: UTF-8 with or without a BOM, else cp1251; the delimiter is the one of «;», «,» and
tab the header line has most of. XLSX is the first sheet of the workbook, read with the
standard library the way the export writes it (``app/services/exports/xlsx.py``): shared and
inline strings, numbers as they were typed. A date typed in Excel is stored as a serial number,
so the column that expects a date turns such a number into a date (``excel_date``). Nothing
here knows what the columns mean: that is ``app/services/contract_import.py``.
"""

import csv
import re
import zipfile
from datetime import date, timedelta
from io import BytesIO, StringIO
from xml.etree import ElementTree

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Day 0 of the serial dates of Excel (the 1900 system with its leap-year bug counted in).
EXCEL_EPOCH = date(1899, 12, 30)
# Serial numbers Excel would show as dates of this century; anything else is a number.
EXCEL_DATE_RANGE = (36526, 73050)

DELIMITERS = (";", ",", "\t")
COLUMN_LETTERS = re.compile(r"^([A-Z]+)")

UNSUPPORTED = "Поддерживаются файлы CSV и XLSX"
NOT_XLSX = "Файл не является книгой XLSX"


class TableError(ValueError):
    """The file is not a table this import can read; the message is for the person."""


def read_table(content: bytes, file_name: str) -> list[list[str]]:
    """Rows of the file, cells as stripped strings; the first row is the header."""
    name = file_name.lower()
    if name.endswith(".xlsx"):
        return read_xlsx(content)
    if name.endswith(".csv"):
        return read_csv(content)
    raise TableError(UNSUPPORTED)


# --- CSV -----------------------------------------------------------------------------------


def decode(content: bytes) -> str:
    """UTF-8 (a BOM dropped) when it is UTF-8, else cp1251 — the other encoding Excel saves in."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1251")


def delimiter_of(line: str) -> str:
    """The delimiter the header has most of; «;» when it has none of them."""
    return max(DELIMITERS, key=lambda candidate: (line.count(candidate), candidate == ";"))


def read_csv(content: bytes) -> list[list[str]]:
    text = decode(content)
    first_line = text.splitlines()[0] if text.strip() else ""
    reader = csv.reader(StringIO(text), delimiter=delimiter_of(first_line))
    return [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]


# --- XLSX ----------------------------------------------------------------------------------


def column_index(reference: str) -> int:
    """0-based index of the column of a cell reference: A1 → 0, Z9 → 25, AA1 → 26."""
    match = COLUMN_LETTERS.match(reference)
    index = 0
    for letter in match.group(1) if match else "A":
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def first_sheet_path(archive: zipfile.ZipFile) -> str:
    """Part of the first sheet of the workbook, by its relationship; the usual name otherwise."""
    try:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return "xl/worksheets/sheet1.xml"
    sheet = workbook.find(f"{MAIN_NS}sheets/{MAIN_NS}sheet")
    wanted = None if sheet is None else sheet.get(f"{REL_NS}id")
    for relationship in relationships.iter(f"{PKG_NS}Relationship"):
        if relationship.get("Id") == wanted:
            target = relationship.get("Target", "")
            return target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    return "xl/worksheets/sheet1.xml"


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in item.iter(f"{MAIN_NS}t")) for item in root]


def cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{MAIN_NS}t"))
    value = cell.find(f"{MAIN_NS}v")
    text = "" if value is None or value.text is None else value.text
    if kind == "s":
        try:
            return shared[int(text)]
        except (ValueError, IndexError):
            return ""
    return text


def read_xlsx(content: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except zipfile.BadZipFile as error:
        raise TableError(NOT_XLSX) from error
    with archive:
        try:
            shared = shared_strings(archive)
            sheet = ElementTree.fromstring(archive.read(first_sheet_path(archive)))
        except (KeyError, ElementTree.ParseError) as error:
            raise TableError(NOT_XLSX) from error
    rows: list[list[str]] = []
    for row in sheet.iter(f"{MAIN_NS}row"):
        cells = {
            column_index(cell.get("r", "")): cell_text(cell, shared).strip()
            for cell in row.findall(f"{MAIN_NS}c")
        }
        if not any(cells.values()):
            continue
        rows.append([cells.get(index, "") for index in range(max(cells) + 1)])
    return rows


def excel_date(serial: float) -> date | None:
    """Date of a serial number of Excel; None for a number that is not a date of this century."""
    if not EXCEL_DATE_RANGE[0] <= serial <= EXCEL_DATE_RANGE[1]:
        return None
    return EXCEL_EPOCH + timedelta(days=int(serial))
