"""Сводка для руководителя: сборка выпуска и его страница PDF (T-67, docs/design/README.md §6.2).

One page of ``Digest.html``: the verdict in a paragraph, the four status counts with the change
over the week, «Требуют решения», «Худшие школы недели», the KPIs of ТЗ п. 4 and the totals of
the incidents. Every number comes from a service that already answers it — ``dashboard_summary``
and ``attention_list`` of T-60, ``schools_availability`` of T-27, ``incident_analytics_report``
of T-45 — so the digest cannot disagree with the panel it summarises. The previous period is the
same call over the week before: the delta of the four numbers is the difference of two selections
counted the same way.

The drawing reuses the generator of the school report (T-32, ``exports/report_pdf.py``): the same
``Layout``, the same fonts, colors and number format, so «предпросмотр совпадает с PDF» is the
same code for the preview, the letter and «Скачать PDF».
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appeal, Region
from app.schemas.dashboard import AttentionItem, DashboardSummary, SchoolStatusCounts
from app.services.analytics import AnalyticsFilters
from app.services.attention import attention_list
from app.services.availability import schools_availability
from app.services.exports.pdf import PAGE_HEIGHT, PdfDocument
from app.services.exports.report_pdf import (
    BORDER,
    CONTENT_WIDTH,
    MARGIN,
    MUTED,
    NBSP,
    NO_VALUE,
    SECONDARY,
    STATUS_COLORS,
    STATUS_LABELS,
    SURFACE,
    TEXT,
    Column,
    Layout,
    duration,
    fit,
    formatted,
    with_unit,
)
from app.services.incident_analytics import incident_analytics_report
from app.services.notifications import METRIC_TITLES
from app.services.overview import OverviewFilters, dashboard_summary, school_candidates
from app.services.settings import system_settings

# Заголовок выпуска по всей области: подпись, а не настройка (ТЗ п. 1).
OBLAST_TITLE = "Восточно-Казахстанская область"

# Сколько строк показывает каждый список одной страницы (docs/design/README.md §6.2).
WORST_SCHOOLS = 5
DECISIONS = 3

# Период выпуска: неделя, которая заканчивается сейчас (docs/design/README.md §6.2).
PERIOD = timedelta(days=7)

# Почему школа попала в «Худшие школы недели»: причина строки «Требуют внимания» (T-60).
REASON_TITLES = {
    "offline": "нет соединения",
    "critical": "критично",
    "incident_unassigned": "инцидент без ответственного",
    "appeal_unanswered": "обращение без ответа",
}

# Четыре статуса качества ТЗ п. 13 в порядке макета; «Нет данных» — показ, а не статус.
STATUS_ORDER = ("normal", "unstable", "critical", "offline")


@dataclass(frozen=True)
class DigestRow:
    """Строка «Худшие школы недели»: где, кто обслуживает, доступность и что не так."""

    school_name: str
    region_name: str
    provider_name: str | None
    availability_pct: float | None
    problem: str


@dataclass(frozen=True)
class Digest:
    """Выпуск сводки одного охвата за период: всё, что печатается на странице."""

    title: str
    period_from: datetime
    period_to: datetime
    created_at: datetime
    timezone: str
    verdict: str
    counts: SchoolStatusCounts
    previous_counts: SchoolStatusCounts | None
    summary: DashboardSummary
    decisions: list[str]
    worst: list[DigestRow]
    incidents_opened: int
    incidents_restored: int
    avg_restore_s: int | None
    max_restore_s: int | None
    appeals_sent: int


def delta(current: int, previous: int | None) -> str:
    """«▲ 3», «▼ 2», «без изменений»; «первый выпуск», когда сравнивать не с чем."""
    if previous is None:
        return "первый выпуск"
    difference = current - previous
    if difference == 0:
        return "без изменений"
    return f"{'▲' if difference > 0 else '▼'}{NBSP}{abs(difference)} к прошлой неделе"


def verdict_text(
    counts: SchoolStatusCounts, previous: SchoolStatusCounts | None, total: int
) -> str:
    """Вердикт абзацем: сколько школ в норме и куда сдвинулось за неделю (§6.2)."""
    head = f"{counts.normal} школ из {total} в норме."
    if previous is None:
        return f"{head} Это первый выпуск сводки: сравнивать пока не с чем."
    difference = counts.normal - previous.normal
    if difference == 0:
        return f"{head} К прошлой неделе без изменений."
    word = "больше" if difference > 0 else "меньше"
    return f"{head} На {abs(difference)} {word}, чем неделю назад."


def problem_text(item: AttentionItem) -> str:
    """Что не так со школой: причина строки «Требуют внимания» и основание инцидента."""
    reason = REASON_TITLES[item.reason]
    if item.metric is not None:
        return f"{reason}: {METRIC_TITLES[item.metric].lower()}"
    return reason


def decision_lines(items: list[AttentionItem], counts: SchoolStatusCounts) -> list[str]:
    """«Требуют решения» до трёх пунктов: поставщики с наибольшим числом проблем и связь."""
    lines: list[str] = []
    providers = Counter(item.provider_name for item in items if item.provider_name)
    for name, count in providers.most_common(DECISIONS - 1):
        lines.append(f"{name}: школ с проблемами — {count}. Нужен разбор с поставщиком.")
    if counts.offline:
        lines.append(f"Без связи {counts.offline} школ: проверьте линии и агентов.")
    elif counts.critical:
        lines.append(f"Критично в {counts.critical} школах: показатели ниже порогов.")
    if not lines:
        lines.append("Решений не требуется: показатели школ в пределах порогов.")
    return lines[:DECISIONS]


async def scope_title(session: AsyncSession, region_id: int | None) -> str:
    """Заголовок выпуска: наименование района или всей области."""
    if region_id is None:
        return OBLAST_TITLE
    name = await session.scalar(select(Region.name).where(Region.id == region_id))
    return name or OBLAST_TITLE


async def build_digest(session: AsyncSession, *, region_id: int | None, now: datetime) -> Digest:
    """Выпуск сводки по охвату за неделю, которая заканчивается в ``now``.

    Область видимости запросов — сессия вызывающего: у рассылки её задаёт ``region_id``, а у
    предпросмотра — ещё и RLS роли панели (ADR-008).
    """
    settings = await system_settings(session)
    filters = OverviewFilters(region_id=region_id)
    period_from = now - PERIOD
    summary = await dashboard_summary(session, filters, period_from=period_from, period_to=now)
    earlier = await dashboard_summary(
        session, filters, period_from=period_from - PERIOD, period_to=period_from
    )
    seen = earlier.measurements_count or earlier.devices_count
    previous = earlier.status_counts if seen else None

    attention = await attention_list(session, filters, now=now, limit=WORST_SCHOOLS)
    availability = await schools_availability(
        session, [item.school_id for item in attention.items], start=period_from, end=now
    )
    worst = [
        DigestRow(
            school_name=item.school_name,
            region_name=item.region_name,
            provider_name=item.provider_name,
            availability_pct=availability[item.school_id].uptime_pct,
            problem=problem_text(item),
        )
        for item in attention.items
    ]

    incidents = await incident_analytics_report(
        session,
        "region",
        AnalyticsFilters(region_id=region_id),
        period="custom",
        period_from=period_from,
        period_to=now,
        now=now,
    )
    row = incidents.rows[0] if incidents.rows else None
    appeals = await session.scalar(
        select(func.count())
        .select_from(Appeal)
        .where(
            Appeal.school_id.in_(school_candidates(filters)),
            Appeal.sent_at >= period_from,
            Appeal.sent_at < now,
        )
    )

    return Digest(
        title=await scope_title(session, region_id),
        period_from=period_from,
        period_to=now,
        created_at=now,
        timezone=settings.timezone,
        verdict=verdict_text(summary.status_counts, previous, summary.schools_count),
        counts=summary.status_counts,
        previous_counts=previous,
        summary=summary,
        decisions=decision_lines(attention.items, summary.status_counts),
        worst=worst,
        incidents_opened=row.incidents_count if row else 0,
        incidents_restored=row.restored_count if row else 0,
        avg_restore_s=row.avg_duration_s if row else None,
        max_restore_s=row.max_duration_s if row else None,
        appeals_sent=appeals or 0,
    )


# --- Страница PDF: тот же генератор, что отчёт по школе (T-32) ------------------------------


def digest_header(layout: Layout, digest: Digest) -> None:
    zone = ZoneInfo(digest.timezone)
    first = digest.period_from.astimezone(zone)
    last = (digest.period_to - timedelta(seconds=1)).astimezone(zone)
    layout.y += 10
    layout.text(MARGIN, layout.y, "Еженедельная сводка для руководителя", 9, SECONDARY)
    layout.y += 26
    title = fit(layout.font, digest.title, CONTENT_WIDTH, 19)
    layout.text(MARGIN, layout.y, title, 19, TEXT, bold=True)
    layout.y += 4
    layout.paragraph(
        f"Выпуск за {first:%d.%m.%Y} — {last:%d.%m.%Y} · время {digest.timezone} · "
        f"сформирован {digest.created_at.astimezone(zone):%d.%m.%Y %H:%M}",
        9.5,
        SECONDARY,
    )
    layout.y += 8
    layout.page.line(MARGIN, layout.y, MARGIN + CONTENT_WIDTH, layout.y, BORDER)
    layout.paragraph(digest.verdict, 11, TEXT)


def digest_counts(layout: Layout, digest: Digest) -> None:
    """Четыре числа статусов с дельтой к прошлой неделе (ТЗ п. 13)."""
    gap, height = 8.0, 54.0
    width = (CONTENT_WIDTH - 3 * gap) / 4
    layout.y += 18
    top = layout.y
    layout.y += height
    for index, status in enumerate(STATUS_ORDER):
        current = getattr(digest.counts, status)
        previous = getattr(digest.previous_counts, status) if digest.previous_counts else None
        x = MARGIN + (width + gap) * index
        layout.page.rectangle(x, top, width, height, SURFACE)
        layout.page.rectangle(x, top, 3, height, STATUS_COLORS[status])
        layout.text(x + 10, top + 15, STATUS_LABELS[status], 8, SECONDARY)
        layout.text(x + 10, top + 34, formatted(current, 0), 15, TEXT, bold=True)
        change = fit(layout.font, delta(current, previous), width - 18, 7.5)
        layout.text(x + 10, top + 46, change, 7.5, MUTED)
    layout.paragraph(
        f"Школ по фильтрам: {digest.summary.schools_count} из {digest.summary.schools_total_count} "
        f"в реестре · «Нет данных»: {digest.counts.no_data}",
        8,
        MUTED,
    )


def digest_kpis(layout: Layout, digest: Digest) -> None:
    """Строка показателей ТЗ п. 4 за период выпуска."""
    summary = digest.summary
    layout.heading("Показатели за неделю", room=60)
    tiles = [
        ("Замеров", formatted(summary.measurements_count, 0)),
        ("Средний Download", with_unit(summary.avg_download_mbps, "Мбит/с", 1)),
        ("Средний Upload", with_unit(summary.avg_upload_mbps, "Мбит/с", 1)),
        ("Средний Ping", with_unit(summary.avg_ping_ms, "мс", 0)),
        ("Компьютеров на связи", f"{summary.active_devices_count} из {summary.devices_count}"),
        ("Проблемных компьютеров", formatted(summary.problem_devices_count, 0)),
    ]
    gap, height = 8.0, 42.0
    width = (CONTENT_WIDTH - 5 * gap) / 6
    layout.y += 10
    top = layout.y
    layout.y += height
    for index, (label, value) in enumerate(tiles):
        x = MARGIN + (width + gap) * index
        layout.page.rectangle(x, top, width, height, SURFACE)
        layout.text(x + 7, top + 14, fit(layout.font, label, width - 14, 7.5), 7.5, SECONDARY)
        layout.text(x + 7, top + 31, fit(layout.font, value, width - 14, 11), 11, TEXT, bold=True)


def digest_decisions(layout: Layout, digest: Digest) -> None:
    layout.heading("Требуют решения", room=50)
    for number, line in enumerate(digest.decisions, start=1):
        layout.paragraph(f"{number}. {line}", 9.5, TEXT)


def digest_worst(layout: Layout, digest: Digest) -> None:
    layout.heading("Худшие школы недели", room=60)
    if not digest.worst:
        layout.paragraph("Школ, требующих внимания, за неделю не было.")
        return
    layout.table(
        [
            Column("Школа", 150),
            Column("Район", 110),
            Column("Поставщик", 100),
            Column("Доступность", 60, right=True),
            Column("Проблема", 95.28),
        ],
        [
            [
                row.school_name,
                row.region_name,
                row.provider_name or NO_VALUE,
                with_unit(row.availability_pct, "%", 1).replace(f"{NBSP}%", "%"),
                row.problem,
            ]
            for row in digest.worst
        ],
    )


def digest_incidents(layout: Layout, digest: Digest) -> None:
    layout.heading("Инциденты и обращения", room=40)
    parts = [
        f"открыто {digest.incidents_opened}",
        f"восстановлено {digest.incidents_restored}",
        "среднее восстановление "
        + (duration(digest.avg_restore_s) if digest.avg_restore_s is not None else NO_VALUE),
        "самое долгое "
        + (duration(digest.max_restore_s) if digest.max_restore_s is not None else NO_VALUE),
        f"обращений отправлено {digest.appeals_sent}",
    ]
    layout.paragraph(" · ".join(parts), 9.5, TEXT)


def digest_footer(document: PdfDocument, digest: Digest) -> None:
    font = document.font
    for page in document.pages:
        y = PAGE_HEIGHT - 32
        page.line(MARGIN, y - 12, MARGIN + CONTENT_WIDTH, y - 12, BORDER)
        zone = ZoneInfo(digest.timezone)
        name = fit(font, f"Мониторинг интернета · {digest.title}", 400, 7.5)
        stamp = f"{digest.created_at.astimezone(zone):%d.%m.%Y %H:%M}"
        page.text(MARGIN, y, name, size=7.5, color=MUTED)
        page.text(MARGIN + CONTENT_WIDTH - font.width(stamp, 7.5), y, stamp, size=7.5, color=MUTED)


def digest_pdf(digest: Digest) -> bytes:
    """Одна страница A4 выпуска: та же вёрстка, что предпросмотр панели (§6.2)."""
    document = PdfDocument(f"Сводка для руководителя — {digest.title}")
    layout = Layout(document)
    digest_header(layout, digest)
    digest_counts(layout, digest)
    digest_kpis(layout, digest)
    digest_decisions(layout, digest)
    digest_worst(layout, digest)
    digest_incidents(layout, digest)
    digest_footer(document, digest)
    return document.to_bytes()


def digest_file_name(digest: Digest) -> str:
    """Имя файла письма и выгрузки: «svodka-2026-09-21.pdf»."""
    return f"svodka-{digest.period_to.astimezone(ZoneInfo(digest.timezone)):%Y-%m-%d}.pdf"


def digest_message(digest: Digest) -> tuple[str, str]:
    """Тема письма и короткий текст сообщения: то же, что печатает страница."""
    zone = ZoneInfo(digest.timezone)
    last = (digest.period_to - timedelta(seconds=1)).astimezone(zone)
    subject = f"Сводка по интернету в школах · {digest.title} · неделя до {last:%d.%m.%Y}"
    lines = (f"{number}. {line}" for number, line in enumerate(digest.decisions, start=1))
    body = "\n".join([digest.verdict, *lines])
    return subject, body
