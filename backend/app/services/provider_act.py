"""Claim act against a provider as one PDF (T-68; ТЗ п. 11, п. 14; docs/design/README.md §6.3).

Drawn by the generator of the appeal of T-48 (``app/services/exports/report_pdf.py``): A4, the
embedded DejaVu Sans for the Cyrillic, the light tokens of DESIGN.md.

Every measurement the act argues from carries the thresholds and the contract values that were
applied to it — they are read from ``measurements.thresholds_snapshot``, never from the profile
or the contract of today (ТЗ п. 11, ADR-004). That is the whole point of the document: a change
of the profile or a new contract signed later must not move the ground a claim already stands
on. A line without a snapshot is not argued from at all.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, Measurement, Region, School
from app.schemas.analytics import AnalyticsPeriod
from app.schemas.providers import ProviderScoreDetail
from app.services.exports.pdf import PAGE_HEIGHT, PdfDocument
from app.services.exports.report_pdf import (
    BORDER,
    CONTENT_WIDTH,
    MARGIN,
    MUTED,
    NO_VALUE,
    SECONDARY,
    TEXT,
    Column,
    Layout,
    fit,
    formatted,
    wrap,
)
from app.services.provider_score import provider_score_detail, score_window
from app.services.settings import system_settings

# Rows of the table: an act is read and signed by people, so it argues from the measurements of
# the period, not from all of them. The summary counts every one of them.
ACT_MAX_ROWS = 400

BODY_SIZE = 10.0


@dataclass(frozen=True)
class ActRow:
    """One measurement below the contract, with the numbers it was judged by at its moment."""

    measured_at: datetime
    school_name: str
    region_name: str | None
    download_mbps: float | None
    upload_mbps: float | None
    contract_down_mbps: float | None
    contract_up_mbps: float | None
    download_min_mbps: float | None
    upload_min_mbps: float | None


@dataclass(frozen=True)
class ProviderActDocument:
    """Everything the act shows; the PDF adds nothing of its own."""

    provider_name: str
    detail: ProviderScoreDetail
    rows: list[ActRow]
    below_contract_count: int
    timezone: str
    created_at: datetime


def act_row(row: Any) -> ActRow:
    snapshot = row.thresholds_snapshot or {}
    return ActRow(
        measured_at=row.measured_at,
        school_name=row.school_name,
        region_name=row.region_name,
        download_mbps=row.download_mbps,
        upload_mbps=row.upload_mbps,
        contract_down_mbps=snapshot.get("contract_down_mbps"),
        contract_up_mbps=snapshot.get("contract_up_mbps"),
        download_min_mbps=snapshot.get("download_min_mbps"),
        upload_min_mbps=snapshot.get("upload_min_mbps"),
    )


async def provider_act(
    session: AsyncSession,
    provider_id: int,
    *,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    now: datetime,
) -> ProviderActDocument:
    """The act of one provider over the period; 404 while the user sees none of his lines."""
    settings = await system_settings(session)
    window = score_window(settings, period, period_from, period_to, now=now)
    detail = await provider_score_detail(
        session,
        provider_id,
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=now,
    )
    # RLS of ``lines`` and ``schools`` applies through the joins, as everywhere (ADR-008); only
    # the main lines are argued from, as the score counts them (ТЗ п. 10).
    below = (
        select(
            Measurement.measured_at,
            Measurement.download_mbps,
            Measurement.upload_mbps,
            Measurement.thresholds_snapshot,
            School.full_name.label("school_name"),
            Region.name.label("region_name"),
        )
        .join(Line, Line.id == Measurement.line_id)
        .join(School, School.id == Line.school_id)
        .outerjoin(Region, Region.id == School.region_id)
        .where(
            Line.provider_id == provider_id,
            Line.status == "main",
            Measurement.contract_ok.is_(False),
            Measurement.measured_at >= window.start,
            Measurement.measured_at < window.end,
        )
    )
    counted = await session.scalar(select(func.count()).select_from(below.subquery()))
    rows = await session.execute(below.order_by(Measurement.measured_at).limit(ACT_MAX_ROWS))
    return ProviderActDocument(
        provider_name=detail.provider.name,
        detail=detail,
        rows=[act_row(row) for row in rows],
        below_contract_count=int(counted or 0),
        timezone=settings.timezone,
        created_at=now,
    )


def pair(fact: float | None, promised: float | None) -> str:
    """«17,2 / 50,0»: the fact next to what the contract promised at that moment."""
    return f"{formatted(fact)} / {formatted(promised)}"


def heading(layout: Layout, act: ProviderActDocument) -> None:
    zone = ZoneInfo(act.timezone)
    layout.y += 10
    layout.text(MARGIN, layout.y, "Акт о несоответствии качества услуги", 9, SECONDARY)
    for line in wrap(layout.font, act.provider_name, CONTENT_WIDTH, 17):
        layout.y += 24
        layout.text(MARGIN, layout.y, line, 17, TEXT, bold=True)
    period = (
        f"Период: {act.detail.period_from.astimezone(zone):%d.%m.%Y}"
        f" — {act.detail.period_to.astimezone(zone):%d.%m.%Y}"
        f" · время {act.timezone}"
        f" · составлен {act.created_at.astimezone(zone):%d.%m.%Y %H:%M}"
    )
    layout.y += 6
    layout.paragraph(period, 9.5, SECONDARY)
    layout.y += 10
    layout.page.line(MARGIN, layout.y, MARGIN + CONTENT_WIDTH, layout.y, BORDER)


def summary(layout: Layout, act: ProviderActDocument) -> None:
    row = act.detail.provider
    layout.heading("Итоги периода", room=90)
    score = NO_VALUE if row.score is None else formatted(row.score)
    layout.paragraph(
        f"Школ на основных линиях: {row.schools_count}."
        f" Замеров за период: {row.measurements_count},"
        f" из них ниже договорной скорости: {act.below_contract_count}.",
        BODY_SIZE,
        TEXT,
    )
    layout.paragraph(
        f"Инцидентов начато: {row.incidents_opened}, восстановлено: {row.incidents_closed}."
        f" Оценка поставщика: {score} при пороге {formatted(act.detail.weights.pass_pct)}.",
        BODY_SIZE,
        TEXT,
    )
    layout.paragraph(
        "Пороги и договорные значения в таблице — те, по которым замер был оценён при приёме"
        " (ТЗ п. 11): изменение профиля или нового договора их не меняет.",
        8.5,
        MUTED,
    )


ACT_COLUMNS = [
    Column("Дата и время", 78),
    Column("Школа", 120),
    Column("Район", 78),
    Column("Download, факт / договор", 80, right=True),
    Column("Upload, факт / договор", 80, right=True),
    Column("Порог download, Мбит/с", 79, right=True),
]


def measurements(layout: Layout, act: ProviderActDocument) -> None:
    zone = ZoneInfo(act.timezone)
    layout.heading("Замеры ниже договорной скорости", room=80)
    if not act.rows:
        layout.paragraph("За период таких замеров нет.", BODY_SIZE, SECONDARY)
        return
    if act.below_contract_count > len(act.rows):
        layout.paragraph(
            f"Показаны первые {len(act.rows)} из {act.below_contract_count} замеров;"
            " полный список — выгрузка XLSX за тот же период.",
            8.5,
            MUTED,
        )
    layout.table(
        ACT_COLUMNS,
        [
            [
                f"{row.measured_at.astimezone(zone):%d.%m.%Y %H:%M}",
                row.school_name,
                row.region_name or NO_VALUE,
                pair(row.download_mbps, row.contract_down_mbps),
                pair(row.upload_mbps, row.contract_up_mbps),
                formatted(row.download_min_mbps),
            ]
            for row in act.rows
        ],
    )


SCHOOL_COLUMNS = [
    Column("Школа", 260),
    Column("Замеров за период", 130, right=True),
    Column("Ниже договора, %", 125, right=True),
]


def schools(layout: Layout, act: ProviderActDocument) -> None:
    rows = [row for row in act.detail.schools if row.below_contract_pct]
    if not rows:
        return
    layout.heading("Итоги по школам", room=60)
    layout.table(
        SCHOOL_COLUMNS,
        [
            [
                row.name,
                formatted(row.measurements_count, 0),
                formatted(row.below_contract_pct),
            ]
            for row in rows
        ],
    )


def signatures(layout: Layout) -> None:
    layout.heading("Подписи сторон", room=70)
    layout.paragraph(
        "Со стороны управления образования: ____________________ / ____________________",
        BODY_SIZE,
        TEXT,
    )
    layout.paragraph(
        "Со стороны поставщика услуги: ____________________ / ____________________",
        BODY_SIZE,
        TEXT,
    )
    layout.paragraph("Электронная подпись ставится вне системы.", 8.5, MUTED)


def footers(document: PdfDocument, act: ProviderActDocument) -> None:
    font = document.font
    for number, page in enumerate(document.pages, start=1):
        y = PAGE_HEIGHT - 32
        page.line(MARGIN, y - 12, MARGIN + CONTENT_WIDTH, y - 12, BORDER)
        pages = f"Стр. {number} из {len(document.pages)}"
        name = fit(font, f"Акт о несоответствии · {act.provider_name}", 400, 7.5)
        page.text(MARGIN, y, name, size=7.5, color=MUTED)
        page.text(MARGIN + CONTENT_WIDTH - font.width(pages, 7.5), y, pages, size=7.5, color=MUTED)


def provider_act_pdf(act: ProviderActDocument) -> bytes:
    """The act as one PDF file: the heading, the totals, the measurements and the signatures."""
    document = PdfDocument(f"Акт о несоответствии — {act.provider_name}")
    layout = Layout(document)
    heading(layout, act)
    summary(layout, act)
    measurements(layout, act)
    schools(layout, act)
    signatures(layout)
    footers(document, act)
    return document.to_bytes()
