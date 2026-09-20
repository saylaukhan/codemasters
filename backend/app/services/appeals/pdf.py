"""PDF of a sent appeal (T-48, ТЗ п. 17): the letter as it went to the provider.

Drawn by the generator the school report is drawn by (``app/services/exports/pdf.py``): A4, the
embedded DejaVu Sans for the Cyrillic, the light tokens of DESIGN.md. WeasyPrint of plan.md §2
is not among the dependencies (docs/known-limitations.md, T-32), and the letter needs no page
engine: it is a heading, a few facts and the text.

The text of the letter is the Markdown the person sent (ADR-011): paragraphs, bold, lists and
the rule above the signature. It is drawn as the marks mean, not as the characters look —
``**Провайдер**`` is a bold line, not four asterisks in the middle of a word.
"""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas.appeals import AppealContext
from app.services.appeals.context import AppealFacts
from app.services.appeals.prompt import facts_lines, metric_lines
from app.services.exports.pdf import PAGE_HEIGHT, PdfDocument
from app.services.exports.report_pdf import (
    BORDER,
    CONTENT_WIDTH,
    MARGIN,
    MUTED,
    SECONDARY,
    TEXT,
    Layout,
    fit,
    wrap,
)

# Body of the letter and the facts under it.
BODY_SIZE = 10.0
BULLET_INDENT = 12.0

NO_ADDRESS = "адрес поставщика не указан"


@dataclass(frozen=True)
class AppealLetter:
    """Everything the PDF of an appeal shows; the row of ``appeals`` is built from the same."""

    number: str
    subject: str
    text: str
    user_comment: str | None
    context: AppealContext
    recipient_email: str | None
    sent_at: datetime
    author_name: str
    timezone: str


def clean(line: str) -> str:
    """A Markdown line as it is read aloud: without the ``**``, ``*`` and backticks of marks."""
    return line.replace("**", "").replace("`", "").strip()


def heading(layout: Layout, letter: AppealLetter) -> None:
    zone = ZoneInfo(letter.timezone)
    layout.y += 10
    layout.text(MARGIN, layout.y, "Обращение к поставщику услуги", 9, SECONDARY)
    layout.y += 24
    layout.text(MARGIN, layout.y, letter.number, 17, TEXT, bold=True)
    layout.y += 16
    sent = f"{letter.sent_at.astimezone(zone):%d.%m.%Y %H:%M} ({letter.timezone})"
    address = letter.recipient_email or NO_ADDRESS
    layout.text(MARGIN, layout.y, f"Отправлено {sent} · {address}", 9, SECONDARY)
    layout.y += 6
    for line in wrap(layout.font, letter.subject, CONTENT_WIDTH, 12):
        layout.y += 18
        layout.text(MARGIN, layout.y, line, 12, TEXT, bold=True)
    layout.y += 10
    layout.page.line(MARGIN, layout.y, MARGIN + CONTENT_WIDTH, layout.y, BORDER)


def body(layout: Layout, text: str) -> None:
    """The Markdown of the letter: headings and list items as marks, the rest as paragraphs."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            layout.y += BODY_SIZE * 0.6
            continue
        if set(line) <= {"-", "—", "*", "_"} and len(line) >= 3:
            layout.ensure(12)
            layout.y += 10
            layout.page.line(MARGIN, layout.y, MARGIN + CONTENT_WIDTH, layout.y, BORDER)
            layout.y += 4
            continue
        if line.startswith("#"):
            layout.y += 8
            layout.paragraph(clean(line.lstrip("#")), BODY_SIZE, TEXT)
            continue
        if line.startswith(("- ", "* ")):
            indent = MARGIN + BULLET_INDENT
            for index, part in enumerate(
                wrap(layout.font, clean(line[2:]), CONTENT_WIDTH - BULLET_INDENT, BODY_SIZE)
            ):
                layout.ensure(BODY_SIZE * 1.5)
                layout.y += BODY_SIZE * 1.5
                if index == 0:
                    layout.text(MARGIN + 3, layout.y, "•", BODY_SIZE, SECONDARY)
                layout.text(indent, layout.y, part, BODY_SIZE, TEXT)
            continue
        bold = raw.strip().startswith("**") and raw.strip().endswith("**")
        for part in wrap(layout.font, clean(line), CONTENT_WIDTH, BODY_SIZE):
            layout.ensure(BODY_SIZE * 1.5)
            layout.y += BODY_SIZE * 1.5
            layout.text(MARGIN, layout.y, part, BODY_SIZE, TEXT, bold=bold)


def comment(layout: Layout, value: str) -> None:
    """Comment of the person who sent the appeal: next to the letter, not inside it (ТЗ п. 17)."""
    layout.heading("Комментарий отправителя", room=40)
    for line in value.splitlines():
        if line.strip():
            layout.paragraph(line.strip(), BODY_SIZE, TEXT)


def appendix(layout: Layout, letter: AppealLetter) -> None:
    """Facts the letter argues by, as the appeal keeps them (ТЗ п. 17): the provider checks
    the numbers against the same lines the model was given."""
    facts = AppealFacts(
        context=letter.context,
        excerpt=[],
        recipient_email=letter.recipient_email,
        timezone=letter.timezone,
    )
    layout.heading("Факты обращения", room=80)
    for line in facts_lines(facts):
        layout.paragraph(line, 9, SECONDARY)
    layout.y += 4
    for line in metric_lines(letter.context):
        layout.paragraph(line.lstrip("- "), 9, SECONDARY)


def footers(document: PdfDocument, letter: AppealLetter) -> None:
    font = document.font
    for number, page in enumerate(document.pages, start=1):
        y = PAGE_HEIGHT - 32
        page.line(MARGIN, y - 12, MARGIN + CONTENT_WIDTH, y - 12, BORDER)
        pages = f"Стр. {number} из {len(document.pages)}"
        name = fit(font, f"{letter.number} · {letter.context.school_name}", 400, 7.5)
        page.text(MARGIN, y, name, size=7.5, color=MUTED)
        page.text(MARGIN + CONTENT_WIDTH - font.width(pages, 7.5), y, pages, size=7.5, color=MUTED)


def appeal_pdf(letter: AppealLetter) -> bytes:
    """The letter as one PDF file: the heading, the text, the comment and the facts."""
    document = PdfDocument(f"{letter.number} — {letter.subject}")
    layout = Layout(document)
    heading(layout, letter)
    body(layout, letter.text)
    if letter.user_comment:
        comment(layout, letter.user_comment)
    appendix(layout, letter)
    footers(document, letter)
    return document.to_bytes()
