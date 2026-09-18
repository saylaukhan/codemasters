"""Drawing of the school report (T-32, plan.md §12): header, KPI, charts, downtime, measurements.

A4 portrait, the words and statuses of the panel (``columns.py`` repeats ``labels.ts``,
ADR-013), numbers as ``web/src/lib/format.ts`` writes them: a decimal comma, «4 ч 12 мин». The
colors are the light tokens of DESIGN.md (``web/src/styles/tokens.css``): paper has one theme.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.services.exports.columns import AGGREGATE_COLUMN_TITLES, COLUMN_TITLES, VALUE_LABELS
from app.services.exports.pdf import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    Color,
    Page,
    PdfDocument,
    TrueTypeFont,
    hex_color,
)
from app.services.exports.report import SchoolReport

TEXT = hex_color("#1f2328")  # --text-primary
SECONDARY = hex_color("#5f6670")  # --text-secondary
MUTED = hex_color("#9aa0a8")  # --text-muted
BORDER = hex_color("#e3e5e8")  # --border
SURFACE = hex_color("#f5f6f7")  # --bg-page
GRID = hex_color("#eff1f3")  # --chart-grid
DOWNLOAD = hex_color("#1db866")  # --chart-series-1
STATUS_COLORS: dict[str, Color] = {
    "normal": hex_color("#1db866"),  # --status-normal-main
    "unstable": hex_color("#f5a300"),  # --status-unstable-main
    "critical": hex_color("#e5484d"),  # --status-critical-main
    "offline": hex_color("#8a9099"),  # --status-offline-main
}
STATUS_LABELS = VALUE_LABELS["quality_status"]

MARGIN = 40.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
# Content ends above the footer.
BOTTOM = PAGE_HEIGHT - 56
NBSP = "\u00a0"
NO_VALUE = "—"


def formatted(value: float | None, digits: int = 1) -> str:
    """«1 234,5» as ``formatNumber`` of the panel, a half rounded up as Intl does; «—» for
    nothing."""
    if value is None or not math.isfinite(value):
        return NO_VALUE
    rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), ROUND_HALF_UP)
    return f"{rounded:,.{digits}f}".replace(",", NBSP).replace(".", ",")


def with_unit(value: float | None, unit: str, digits: int) -> str:
    text = formatted(value, digits)
    return text if text == NO_VALUE else f"{text}{NBSP}{unit}"


def duration(seconds: float) -> str:
    """«4 ч 12 мин», «2 д 3 ч», «15 мин» as ``formatDuration`` of the panel."""
    minutes = int(seconds // 60)
    if minutes < 1:
        return "меньше минуты"
    days, hours, rest = minutes // 1440, minutes % 1440 // 60, minutes % 60
    if days:
        return f"{days}{NBSP}д {hours}{NBSP}ч" if hours else f"{days}{NBSP}д"
    if hours:
        return f"{hours}{NBSP}ч {rest}{NBSP}мин" if rest else f"{hours}{NBSP}ч"
    return f"{rest}{NBSP}мин"


def title(column: str) -> str:
    """«Средний Download» of «Средний Download, Мбит/с»."""
    return AGGREGATE_COLUMN_TITLES[column].split(", ")[0]


def fit(font: TrueTypeFont, text: str, width: float, size: float) -> str:
    """``text`` cut with «…» to ``width``."""
    if font.width(text, size) <= width:
        return text
    while text and font.width(text + "…", size) > width:
        text = text[:-1]
    return text + "…"


def wrap(font: TrueTypeFont, text: str, width: float, size: float) -> list[str]:
    """Lines of ``text`` broken between words to ``width``."""
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}" if current else word
        if current and font.width(candidate, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return [*lines, current]


def nice_step(maximum: float, ticks: int = 4) -> float:
    """Step of the value axis: 1, 2, 2.5 or 5 times a power of ten."""
    raw = maximum / ticks
    power = 10 ** math.floor(math.log10(raw))
    return next(power * factor for factor in (1, 2, 2.5, 5, 10) if power * factor >= raw)


@dataclass(frozen=True)
class Column:
    title: str
    width: float
    right: bool = False


# A table cell: its text and, for a status, the color of its dot.
type TableCell = str | tuple[str, Color]


class Layout:
    """A cursor that runs down the pages: whatever does not fit starts a new page."""

    def __init__(self, document: PdfDocument) -> None:
        self.document = document
        self.font = document.font
        self.page: Page = document.new_page()
        self.y = MARGIN

    def ensure(self, height: float) -> bool:
        """A new page unless ``height`` fits on this one; True when it had to start one."""
        if self.y + height <= BOTTOM:
            return False
        self.page = self.document.new_page()
        self.y = MARGIN
        return True

    def text(
        self, x: float, baseline: float, value: str, size: float, color: Color = TEXT, **kw: bool
    ) -> None:
        self.page.text(x, baseline, value, size=size, color=color, **kw)

    def right_text(
        self, right: float, baseline: float, value: str, size: float, color: Color
    ) -> None:
        self.text(right - self.font.width(value, size), baseline, value, size, color)

    def paragraph(self, value: str, size: float = 9, color: Color = SECONDARY) -> None:
        for line in wrap(self.font, value, CONTENT_WIDTH, size):
            self.ensure(size * 1.5)
            self.y += size * 1.5
            self.text(MARGIN, self.y, line, size, color)

    def heading(self, value: str, *, room: float = 100) -> None:
        """Section title, kept on one page with ``room`` of what follows it."""
        self.ensure(34 + room)
        self.y += 26
        self.text(MARGIN, self.y, value, 13, TEXT, bold=True)
        self.y += 4

    def table(self, columns: Sequence[Column], rows: Sequence[Sequence[TableCell]]) -> None:
        """Rows under a header that repeats on every page; «Мбит/с» of a title goes under it."""
        size, row_height, header_height = 7.5, 13.0, 24.0

        def header() -> None:
            self.page.rectangle(MARGIN, self.y, CONTENT_WIDTH, header_height, SURFACE)
            x = MARGIN
            for column in columns:
                lines = column.title.split(", ", 1)
                for index, line in enumerate(lines):
                    baseline = self.y + (10 if len(lines) > 1 else 14) + 9 * index
                    text = fit(self.font, line, column.width - 6, size)
                    if column.right:
                        self.right_text(x + column.width - 3, baseline, text, size, SECONDARY)
                    else:
                        self.text(x + 3, baseline, text, size, SECONDARY)
                x += column.width
            self.y += header_height

        # The header never stays alone at the bottom of a page: a few rows go with it.
        self.ensure(header_height + row_height * min(len(rows), 3))
        header()
        for row in rows:
            if self.ensure(row_height):
                header()
            x = MARGIN
            baseline = self.y + 9.5
            for column, cell in zip(columns, row, strict=True):
                value, dot = (cell, None) if isinstance(cell, str) else cell
                left = x + 3
                if dot is not None:
                    self.page.rectangle(left, baseline - 5.5, 5, 5, dot)
                    left += 8
                text = fit(self.font, value, x + column.width - 3 - left, size)
                if column.right:
                    self.right_text(x + column.width - 3, baseline, text, size, TEXT)
                else:
                    self.text(left, baseline, text, size, TEXT)
                x += column.width
            self.y += row_height
            self.page.line(MARGIN, self.y, MARGIN + CONTENT_WIDTH, self.y, BORDER)

    def bar_chart(
        self, title_text: str, labels: Sequence[str], bars: Sequence[Sequence[tuple[float, Color]]]
    ) -> None:
        """Bars of stacked parts, one per label; the value axis on the left."""
        height, axis = 120.0, 36.0
        self.ensure(height + 44)
        self.y += 16
        self.text(MARGIN, self.y, title_text, 10, TEXT, bold=True)
        top = self.y + 10
        bottom = top + height
        left = MARGIN + axis
        width = CONTENT_WIDTH - axis
        maximum = max((sum(value for value, _ in bar) for bar in bars), default=0)
        if maximum <= 0:
            self.page.rectangle(left, top, width, height, SURFACE)
            message = "Замеров за период нет"
            self.text(
                left + (width - self.font.width(message, 9)) / 2,
                top + height / 2,
                message,
                9,
                MUTED,
            )
        else:
            step = nice_step(maximum)
            ticks = math.ceil(maximum / step)
            for tick in range(ticks + 1):
                y = bottom - height * tick / ticks
                self.page.line(left, y, left + width, y, GRID if tick else BORDER)
                self.right_text(
                    left - 4, y + 2.5, formatted(step * tick, 0 if step >= 1 else 1), 7, MUTED
                )
            slot = width / len(bars)
            bar_width = min(slot * 0.6, 24)
            for index, bar in enumerate(bars):
                x = left + slot * index + (slot - bar_width) / 2
                y = bottom
                for value, color in bar:
                    part = height * value / (step * ticks)
                    if part > 0:
                        self.page.rectangle(x, y - part, bar_width, part, color)
                    y -= part
        every = max(1, math.ceil(len(labels) * 34 / width))
        slot = width / max(len(labels), 1)
        for index, label in enumerate(labels):
            if index % every == 0:
                center = left + slot * index + slot / 2
                self.text(center - self.font.width(label, 7) / 2, bottom + 11, label, 7, MUTED)
        self.y = bottom + 16


def header(layout: Layout, report: SchoolReport) -> None:
    font = layout.font
    layout.y += 10
    layout.text(MARGIN, layout.y, "Отчёт о качестве интернета", 9, SECONDARY)
    for line in wrap(font, report.school_name, CONTENT_WIDTH, 17):
        layout.y += 24
        layout.text(MARGIN, layout.y, line, 17, TEXT, bold=True)
    place = [f"School ID {report.school_code}", report.region_name]
    if report.address:
        place.append(report.address)
    layout.y += 4
    layout.paragraph(" · ".join(place), 9.5, SECONDARY)
    period = (
        f"Период: {report.first_day:%d.%m.%Y} — {report.last_day:%d.%m.%Y} · "
        f"время {report.timezone} · сформирован {report.created_at:%d.%m.%Y %H:%M}"
    )
    layout.paragraph(period, 9.5, SECONDARY)
    layout.y += 10
    layout.page.line(MARGIN, layout.y, MARGIN + CONTENT_WIDTH, layout.y, BORDER)


def kpis(layout: Layout, report: SchoolReport) -> None:
    layout.heading("Основные показатели", room=130)
    layout.paragraph("Основная линия без Wi‑Fi — так же считает аналитика панели.", 8, MUTED)
    record = report.kpis or {}
    count = record.get("measurements_count", 0)
    tiles = [
        (title("measurements_count"), formatted(count, 0), "замеров за период"),
        (title("avg_download_mbps"), with_unit(record.get("avg_download_mbps"), "Мбит/с", 1), ""),
        (title("min_download_mbps"), with_unit(record.get("min_download_mbps"), "Мбит/с", 1), ""),
        (title("avg_upload_mbps"), with_unit(record.get("avg_upload_mbps"), "Мбит/с", 1), ""),
        (title("avg_ping_ms"), with_unit(record.get("avg_ping_ms"), "мс", 0), ""),
        (
            title("problem_pct"),
            with_unit(record.get("problem_pct"), "%", 1).replace(f"{NBSP}%", "%"),
            f"{record.get('problem_count', 0)} из {count} замеров",
        ),
        (
            "Доступность",
            with_unit(report.availability_pct, "%", 1).replace(f"{NBSP}%", "%"),
            "в рабочие часы",
        ),
        (
            "Простои",
            formatted(len(report.downtimes), 0),
            f"суммарно {duration(report.downtime_s)}" if report.downtimes else "не было",
        ),
    ]
    gap, height = 8.0, 54.0
    width = (CONTENT_WIDTH - 3 * gap) / 4
    for index, (label, value, caption) in enumerate(tiles):
        if index % 4 == 0:
            layout.y += 10 if index == 0 else gap
            top = layout.y
            layout.y += height
        x = MARGIN + (width + gap) * (index % 4)
        layout.page.rectangle(x, top, width, height, SURFACE)
        layout.text(x + 8, top + 14, fit(layout.font, label, width - 16, 8), 8, SECONDARY)
        layout.text(x + 8, top + 33, fit(layout.font, value, width - 16, 14), 14, TEXT, bold=True)
        if caption:
            layout.text(x + 8, top + 46, fit(layout.font, caption, width - 16, 7.5), 7.5, MUTED)


def charts(layout: Layout, report: SchoolReport) -> None:
    layout.heading("Графики", room=170)
    labels = [f"{day.day:%d.%m}" for day in report.days]
    layout.bar_chart(
        "Средний Download по дням, Мбит/с",
        labels,
        [[(day.avg_download_mbps or 0.0, DOWNLOAD)] for day in report.days],
    )
    layout.y += 6
    layout.bar_chart(
        "Замеры по статусам по дням",
        labels,
        [
            [(float(day.statuses[status]), color) for status, color in STATUS_COLORS.items()]
            for day in report.days
        ],
    )
    x = MARGIN + 36
    layout.y += 6
    for status, color in STATUS_COLORS.items():
        layout.page.rectangle(x, layout.y - 6, 7, 7, color)
        layout.text(x + 10, layout.y, STATUS_LABELS[status], 8, SECONDARY)
        x += 20 + layout.font.width(STATUS_LABELS[status], 8)


def downtimes(layout: Layout, report: SchoolReport) -> None:
    layout.heading("Простои")
    if not report.downtimes:
        layout.paragraph("Простоев за период нет: агенты не сообщали об отсутствии связи.")
        return
    layout.paragraph(
        f"Простоев: {len(report.downtimes)}, суммарно {duration(report.downtime_s)}. "
        "По отчётам агентов об отсутствии связи; одновременные отчёты нескольких компьютеров "
        "считаются одним простоем.",
    )
    layout.y += 6
    zone = report.created_at.tzinfo
    layout.table(
        [Column("Начало", 170), Column("Окончание", 170), Column("Длительность", 175.28)],
        [
            [
                f"{downtime.started_at.astimezone(zone):%d.%m.%Y %H:%M}",
                "продолжается"
                if downtime.ongoing
                else f"{downtime.ended_at.astimezone(zone):%d.%m.%Y %H:%M}",
                duration(downtime.duration_s),
            ]
            for downtime in report.downtimes
        ],
    )


# Columns of the table of measurements: the minimum of ТЗ п. 9 and the line (п. 10).
MEASUREMENT_COLUMNS = [
    ("date", 49.0),
    ("time", 31.0),
    ("hostname", 71.28),
    ("room", 46.0),
    ("line_status", 47.0),
    ("download_mbps", 44.0),
    ("upload_mbps", 36.0),
    ("ping_ms", 30.0),
    ("jitter_ms", 30.0),
    ("packet_loss_pct", 52.0),
    ("quality_status", 79.0),
]
NUMBER_DIGITS = {
    "download_mbps": 1,
    "upload_mbps": 1,
    "ping_ms": 0,
    "jitter_ms": 0,
    "packet_loss_pct": 1,
}


def measurement_cell(column: str, record: dict[str, Any]) -> TableCell:
    value = record[column]
    if value is None:
        return NO_VALUE
    if column in NUMBER_DIGITS:
        return formatted(float(value), NUMBER_DIGITS[column])
    if column == "quality_status":
        return STATUS_LABELS[str(value)], STATUS_COLORS[str(value)]
    if column in VALUE_LABELS:
        return VALUE_LABELS[column].get(str(value), str(value))
    if column == "date":
        year, month, day = str(value).split("-")
        return f"{day}.{month}.{year}"
    if column == "time":
        return str(value)[:5]
    return str(value)


def measurements(layout: Layout, report: SchoolReport) -> None:
    layout.heading("Замеры")
    if not report.measurements:
        layout.paragraph("Замеров за период нет.")
        return
    layout.paragraph(
        f"Все замеры школы за период ({formatted(len(report.measurements), 0)}): все линии и "
        f"интерфейсы, время {report.timezone}.",
    )
    layout.y += 6
    layout.table(
        [
            Column(COLUMN_TITLES[column], width, right=column in NUMBER_DIGITS)
            for column, width in MEASUREMENT_COLUMNS
        ],
        [
            [measurement_cell(column, record) for column, _ in MEASUREMENT_COLUMNS]
            for record in report.measurements
        ],
    )


def footers(document: PdfDocument, report: SchoolReport) -> None:
    font = document.font
    for number, page in enumerate(document.pages, start=1):
        y = PAGE_HEIGHT - 32
        page.line(MARGIN, y - 12, MARGIN + CONTENT_WIDTH, y - 12, BORDER)
        pages = f"Стр. {number} из {len(document.pages)}"
        name = fit(font, f"{report.school_name} · School ID {report.school_code}", 400, 7.5)
        page.text(MARGIN, y, name, size=7.5, color=MUTED)
        page.text(MARGIN + CONTENT_WIDTH - font.width(pages, 7.5), y, pages, size=7.5, color=MUTED)


def report_pdf(report: SchoolReport) -> bytes:
    document = PdfDocument(f"Отчёт о качестве интернета — {report.school_name}")
    layout = Layout(document)
    header(layout, report)
    kpis(layout, report)
    charts(layout, report)
    downtimes(layout, report)
    measurements(layout, report)
    footers(document, report)
    return document.to_bytes()
