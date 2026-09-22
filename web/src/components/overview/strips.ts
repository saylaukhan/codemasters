// Two strips of the main screen (DESIGN.md §3.10): schools per status and the eight KPIs of ТЗ п. 4.
// Both are built here so the page only places them; the numbers are formatted by lib/format.ts.
import type { DashboardPeriodKpis, DashboardSummary, QualityStatus } from '../../api/types'
import { formatNumber, formatPercent, MS_UNIT, plural, SPEED_UNIT } from '../../lib/format'
import {
  DAY_DELTA_LABELS,
  OVERVIEW_KPI_LABELS,
  OVERVIEW_LABELS,
  SCHOOL_COUNT_FORMS,
} from '../../lib/labels'
import { writeFilters, type MapFilters } from '../map/filters'
import type { KpiStripItem } from '../ui/KpiStrip'
import type { StatusStripItem } from '../ui/StatusStrip'
import { QUALITY_ORDER } from './verdict'

/** The list of schools reads the same filters from the URL, so the column opens it narrowed (§4.1). */
export const schoolsWithStatusPath = (filters: MapFilters, status: QualityStatus): string =>
  `/schools?${writeFilters({ ...filters, status: [status] }).toString()}`

/**
 * Four clickable columns. `previous` of the summary carries the period KPIs only, not the counts
 * per status, so a column has nothing to build a change over the day from and shows none.
 */
export const statusStripItems = (summary: DashboardSummary, filters: MapFilters): StatusStripItem[] =>
  QUALITY_ORDER.map((status) => ({
    status,
    count: summary.statusCounts[status],
    href: schoolsWithStatusPath(filters, status),
  }))

/** «Нет данных: 4 школы» under the columns: a display, not a fifth status (ADR-004). */
export function noDataFootnote(summary: DashboardSummary): string | undefined {
  const count = summary.statusCounts.noData
  if (count === 0) return undefined
  return OVERVIEW_LABELS.noData(formatNumber(count, 0), plural(count, SCHOOL_COUNT_FORMS))
}

type Delta = KpiStripItem['delta']

/** «▲ 1,8», «▼ 3»: green when the metric moved the better way, red when the worse one (§3.10). */
function delta(
  value: number | null,
  earlier: number | null | undefined,
  fractionDigits: number,
  betterWhen: 'more' | 'less',
): Delta {
  if (value === null) return undefined
  if (earlier === null || earlier === undefined) return { text: OVERVIEW_LABELS.firstData, tone: 'neutral' }
  // Rounded first: a change the strip would print as «0» is «без изменений», not a coloured arrow.
  const step = 10 ** fractionDigits
  const change = Math.round((value - earlier) * step) / step
  if (change === 0) return { text: DAY_DELTA_LABELS.none, tone: 'neutral' }
  const arrow = change > 0 ? DAY_DELTA_LABELS.up : DAY_DELTA_LABELS.down
  const better = betterWhen === 'more' ? change > 0 : change < 0
  return { text: `${arrow} ${formatNumber(Math.abs(change), fractionDigits)}`, tone: better ? 'good' : 'bad' }
}

/**
 * The eight KPIs of ТЗ п. 4 in the order of `Main.html`; measurement values cover the main lines
 * without Wi-Fi (ADR-012). The first two have no previous period in the contract, so they carry no
 * delta; the rest compare with `previous` and say «первые данные» while there is none.
 */
export function kpiStripItems(summary: DashboardSummary): KpiStripItem[] {
  const previous: DashboardPeriodKpis | null = summary.previous
  const count = (value: number) => formatNumber(value, 0)
  const online = summary.devicesCount > 0 ? (100 * summary.activeDevicesCount) / summary.devicesCount : null
  return [
    {
      key: 'schools',
      label: OVERVIEW_KPI_LABELS.schools,
      value: count(summary.schoolsCount),
      hint: OVERVIEW_KPI_LABELS.registry(count(summary.schoolsTotalCount)),
    },
    { key: 'devices', label: OVERVIEW_KPI_LABELS.devices, value: count(summary.devicesCount) },
    {
      key: 'activeDevices',
      label: OVERVIEW_KPI_LABELS.activeDevices,
      value: count(summary.activeDevicesCount),
      hint: online === null ? undefined : formatPercent(online),
      delta: delta(summary.activeDevicesCount, previous?.activeDevicesCount, 0, 'more'),
    },
    {
      key: 'measurements',
      label: OVERVIEW_KPI_LABELS.measurements,
      value: count(summary.measurementsCount),
      delta: delta(summary.measurementsCount, previous?.measurementsCount, 0, 'more'),
    },
    {
      key: 'avgDownload',
      label: OVERVIEW_KPI_LABELS.avgDownload,
      value: formatNumber(summary.avgDownloadMbps),
      unit: SPEED_UNIT,
      delta: delta(summary.avgDownloadMbps, previous?.avgDownloadMbps, 1, 'more'),
    },
    {
      key: 'avgUpload',
      label: OVERVIEW_KPI_LABELS.avgUpload,
      value: formatNumber(summary.avgUploadMbps),
      unit: SPEED_UNIT,
      delta: delta(summary.avgUploadMbps, previous?.avgUploadMbps, 1, 'more'),
    },
    {
      key: 'avgPing',
      label: OVERVIEW_KPI_LABELS.avgPing,
      value: formatNumber(summary.avgPingMs, 0),
      unit: MS_UNIT,
      delta: delta(summary.avgPingMs, previous?.avgPingMs, 0, 'less'),
    },
    {
      key: 'problemDevices',
      label: OVERVIEW_KPI_LABELS.problemDevices,
      value: count(summary.problemDevicesCount),
      hint: OVERVIEW_KPI_LABELS.of(count(summary.devicesCount)),
      delta: delta(summary.problemDevicesCount, previous?.problemDevicesCount, 0, 'less'),
    },
  ]
}
