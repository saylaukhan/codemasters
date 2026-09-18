"""The smallest PDF of text, lines and rectangles with an embedded TrueType font (ISO 32000-1).

Cyrillic needs a font inside the file: the 14 standard PDF fonts know Latin only. The font is
DejaVu Sans (``fonts/``, its license next to it), embedded whole as a CIDFontType2 with the
Identity-H encoding: text is written as glyph ids, and the ToUnicode map turns them back into
letters, so a viewer finds and copies the Russian words. Bold is the same glyphs filled and
stroked. Written with the standard library: WeasyPrint of plan.md §2 is not among the
dependencies (docs/known-limitations.md, T-32), as openpyxl is not for ``xlsx.py``.
"""

import struct
import zlib
from functools import cache
from pathlib import Path

type Color = tuple[float, float, float]

FONT_PATH = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
FONT_NAME = "DejaVuSans"
# A4 portrait in points.
PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89


def hex_color(value: str) -> Color:
    """``#1db866`` → the fractions PDF paints with."""
    return (
        int(value[1:3], 16) / 255,
        int(value[3:5], 16) / 255,
        int(value[5:7], 16) / 255,
    )


def u16(data: bytes, offset: int) -> int:
    return int(struct.unpack_from(">H", data, offset)[0])


def i16(data: bytes, offset: int) -> int:
    return int(struct.unpack_from(">h", data, offset)[0])


class TrueTypeFont:
    """Glyph ids and widths of a TrueType font: what a PDF needs to place its text."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        tables = {
            data[12 + 16 * index : 16 + 16 * index].decode("latin-1"): int(
                struct.unpack_from(">I", data, 20 + 16 * index)[0]
            )
            for index in range(u16(data, 4))
        }
        head, hhea, hmtx = tables["head"], tables["hhea"], tables["hmtx"]
        self.units_per_em = u16(data, head + 18)
        self.bbox = [self.scaled(i16(data, head + 36 + 2 * index)) for index in range(4)]
        self.ascent = self.scaled(i16(data, hhea + 4))
        self.descent = self.scaled(i16(data, hhea + 6))
        self.advances = [u16(data, hmtx + 4 * index) for index in range(u16(data, hhea + 34))]
        os2 = tables.get("OS/2")
        self.cap_height = (
            self.scaled(i16(data, os2 + 88)) if os2 and u16(data, os2) >= 2 else self.ascent
        )
        self.glyph_ids = self.character_map(tables["cmap"])
        self.fallback = self.glyph_ids.get(ord("?"), 0)

    def scaled(self, units: int) -> int:
        """Font units → thousandths of the size, the unit of PDF font metrics."""
        return round(units * 1000 / self.units_per_em)

    def character_map(self, cmap: int) -> dict[int, int]:
        """Code point → glyph id from the Unicode BMP subtable (format 4)."""
        data = self.data
        for index in range(u16(data, cmap + 2)):
            platform, encoding = u16(data, cmap + 4 + 8 * index), u16(data, cmap + 6 + 8 * index)
            offset = cmap + int(struct.unpack_from(">I", data, cmap + 8 + 8 * index)[0])
            if (platform, encoding) in {(3, 1), (0, 3)} and u16(data, offset) == 4:
                break
        else:
            raise ValueError("the font has no Unicode BMP character map")
        segments = u16(data, offset + 6) // 2
        ends = offset + 14
        starts = ends + 2 * segments + 2
        deltas = starts + 2 * segments
        ranges = deltas + 2 * segments
        glyphs: dict[int, int] = {}
        for segment in range(segments):
            start, end = u16(data, starts + 2 * segment), u16(data, ends + 2 * segment)
            delta, range_offset = u16(data, deltas + 2 * segment), u16(data, ranges + 2 * segment)
            for code in range(start, min(end, 0xFFFE) + 1):
                if range_offset:
                    address = ranges + 2 * segment + range_offset + 2 * (code - start)
                    glyph = u16(data, address)
                    glyph = (glyph + delta) & 0xFFFF if glyph else 0
                else:
                    glyph = (code + delta) & 0xFFFF
                if glyph:
                    glyphs[code] = glyph
        return glyphs

    def glyph(self, character: str) -> int:
        return self.glyph_ids.get(ord(character), self.fallback)

    def advance(self, glyph: int) -> int:
        """Width of the glyph in thousandths of the size."""
        return self.scaled(self.advances[min(glyph, len(self.advances) - 1)])

    def width(self, text: str, size: float) -> float:
        """Width of ``text`` set in ``size`` points."""
        return sum(self.advance(self.glyph(character)) for character in text) * size / 1000


@cache
def report_font() -> TrueTypeFont:
    return TrueTypeFont(FONT_PATH.read_bytes())


def number(value: float) -> str:
    """A PDF number: no exponent, no trailing zeros."""
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


def color_operands(color: Color) -> str:
    return " ".join(number(part) for part in color)


class Page:
    """Drawing operators of one page; ``y`` is measured from the top edge, as a layout thinks."""

    def __init__(self, document: "PdfDocument") -> None:
        self.document = document
        self.operators: list[str] = []

    def text(
        self,
        x: float,
        baseline: float,
        value: str,
        *,
        size: float,
        color: Color,
        bold: bool = False,
    ) -> None:
        glyphs = self.document.encode(value)
        if not glyphs:
            return
        position = f"{number(x)} {number(PAGE_HEIGHT - baseline)} Td"
        shown = f"BT /F1 {number(size)} Tf {position} <{glyphs}> Tj ET"
        if bold:
            stroke = f"{color_operands(color)} RG {number(size * 0.04)} w 2 Tr"
            self.operators.append(f"q {color_operands(color)} rg {stroke} {shown} Q")
        else:
            self.operators.append(f"{color_operands(color)} rg {shown}")

    def rectangle(self, x: float, top: float, width: float, height: float, color: Color) -> None:
        box = f"{number(x)} {number(PAGE_HEIGHT - top - height)} {number(width)} {number(height)}"
        self.operators.append(f"{color_operands(color)} rg {box} re f")

    def line(
        self, x1: float, y1: float, x2: float, y2: float, color: Color, width: float = 0.5
    ) -> None:
        path = (
            f"{number(x1)} {number(PAGE_HEIGHT - y1)} m {number(x2)} {number(PAGE_HEIGHT - y2)} l"
        )
        self.operators.append(f"{color_operands(color)} RG {number(width)} w {path} S")


def pdf_text(value: str) -> str:
    """A string of the document information: UTF-16 with its byte order mark."""
    return "<" + ("﻿" + value).encode("utf-16-be").hex().upper() + ">"


class PdfDocument:
    """Pages drawn with one font, written as a PDF 1.7 file."""

    def __init__(self, title: str) -> None:
        self.font = report_font()
        self.title = title
        self.pages: list[Page] = []
        # Glyph id → the character it was drawn for: the widths and the ToUnicode map.
        self.used: dict[int, str] = {}

    def new_page(self) -> Page:
        page = Page(self)
        self.pages.append(page)
        return page

    def encode(self, text: str) -> str:
        """Hex glyph ids of ``text``, two bytes each (Identity-H)."""
        glyphs = []
        for character in text:
            glyph = self.font.glyph(character)
            self.used.setdefault(glyph, character)
            glyphs.append(f"{glyph:04X}")
        return "".join(glyphs)

    def to_unicode(self) -> bytes:
        entries = sorted(self.used.items())
        blocks = []
        for start in range(0, len(entries), 100):
            chunk = entries[start : start + 100]
            lines = [
                f"<{glyph:04X}> <{character.encode('utf-16-be').hex().upper()}>"
                for glyph, character in chunk
            ]
            blocks.append(f"{len(chunk)} beginbfchar\n" + "\n".join(lines) + "\nendbfchar")
        return (
            "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            + "\n".join(blocks)
            + "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
        ).encode()

    def to_bytes(self) -> bytes:
        font = self.font
        widths = " ".join(f"{glyph} [{font.advance(glyph)}]" for glyph in sorted(self.used))
        page_ids = [9 + 2 * index for index in range(len(self.pages))]
        objects: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            (
                f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] "
                f"/Count {len(page_ids)} >>"
            ).encode(),
            (
                f"<< /Type /Font /Subtype /Type0 /BaseFont /{FONT_NAME} /Encoding /Identity-H "
                "/DescendantFonts [4 0 R] /ToUnicode 7 0 R >>"
            ).encode(),
            (
                f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{FONT_NAME} "
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                f"/FontDescriptor 5 0 R /CIDToGIDMap /Identity /DW 1000 /W [{widths}] >>"
            ).encode(),
            (
                f"<< /Type /FontDescriptor /FontName /{FONT_NAME} /Flags 32 "
                f"/FontBBox [{' '.join(map(str, font.bbox))}] /ItalicAngle 0 "
                f"/Ascent {font.ascent} /Descent {font.descent} /CapHeight {font.cap_height} "
                "/StemV 80 /FontFile2 6 0 R >>"
            ).encode(),
            stream(font.data, f"/Length1 {len(font.data)}"),
            stream(self.to_unicode()),
            f"<< /Title {pdf_text(self.title)} /Producer (VKO Monitor) >>".encode(),
        ]
        for page in self.pages:
            content_id = len(objects) + 2
            objects.append(
                (
                    f"<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {number(PAGE_WIDTH)} {number(PAGE_HEIGHT)}] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
                ).encode()
            )
            objects.append(stream("\n".join(page.operators).encode()))

        output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for index, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(output)
        output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        output += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
        output += (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 8 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
        return bytes(output)


def stream(data: bytes, extra: str = "") -> bytes:
    """A compressed stream object; ``extra`` goes into its dictionary."""
    packed = zlib.compress(data, 9)
    head = f"<< /Length {len(packed)} /Filter /FlateDecode {extra}".rstrip() + " >>"
    return head.encode() + b"\nstream\n" + packed + b"\nendstream"
