// Verdict of the main screen (DESIGN.md §3.28): one sentence about the whole selection, built from
// the status counts — they are taken before the status filter narrows the schools, so clicking a
// column of the status strip does not rewrite the title (docs/design/README.md §4.1).
import type { DashboardSummary, QualityStatus } from '../../api/types'
import { formatNumber, plural } from '../../lib/format'
import { OVERVIEW_VERDICT_LABELS, SCHOOL_COUNT_FORMS } from '../../lib/labels'

/** The four quality statuses of ТЗ п. 13 in their order; «Нет данных» is not one of them (ADR-004). */
export const QUALITY_ORDER: readonly QualityStatus[] = ['normal', 'unstable', 'critical', 'offline']

/** Every key of the counts, so the five always sum to the selection the filters made. */
const STATUS_ORDER = [...QUALITY_ORDER, 'noData'] as const

/**
 * Schools the verdict speaks about: the whole selection, «Нет данных» included, so the title and
 * «Подключённые школы» of the KPI strip say the same number. `schoolsCount` is not it — the status
 * filter narrows that one, and the counts are taken before it (docs/design/README.md §4.1).
 */
export const selectedSchools = (summary: DashboardSummary): number =>
  STATUS_ORDER.reduce((total, status) => total + summary.statusCounts[status], 0)

const count = (value: number) => formatNumber(value, 0)

/** «312 школ из 350 сегодня в норме»; without the summary — the loading sentence (DESIGN.md §2.7). */
export function overviewVerdict(summary: DashboardSummary | undefined): string {
  if (!summary) return OVERVIEW_VERDICT_LABELS.loading
  const total = selectedSchools(summary)
  if (total === 0) return OVERVIEW_VERDICT_LABELS.empty
  const normal = summary.statusCounts.normal
  const noun = plural(normal, SCHOOL_COUNT_FORMS)
  if (normal === total) return OVERVIEW_VERDICT_LABELS.all(count(total), noun)
  return OVERVIEW_VERDICT_LABELS.part(count(normal), noun, count(total))
}
