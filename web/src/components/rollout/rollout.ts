// Strip and the wording of the rollout screen (T-69, DESIGN.md §3.30): the page only places them.
import type { RolloutFilter, RolloutSchoolItem, RolloutSummary } from '../../api/rollout'
import { formatNumber, formatPercent, formatRelative, NO_VALUE, plural } from '../../lib/format'
import { ROLLOUT_KPI_LABELS, ROLLOUT_LABELS, SCHOOL_COUNT_FORMS } from '../../lib/labels'
import type { KpiStripItem } from '../ui/KpiStrip'

/** Order of the four lists of docs/design/README.md §6.4: the worst news first. */
export const ROLLOUT_FILTERS: readonly RolloutFilter[] = [
  'not_connected',
  'silent',
  'code_unused',
  'old_version',
]

/** How many schools the list holds, for the counter on its chip. */
export const listCount = (summary: RolloutSummary | undefined, filter: RolloutFilter): number | undefined =>
  summary === undefined ? undefined : summary.lists[camelFilter[filter]]

// `lists` of the answer is camelCase, the `filter` of the endpoint is not.
const camelFilter: Record<RolloutFilter, keyof RolloutSummary['lists']> = {
  not_connected: 'notConnected',
  silent: 'silent',
  code_unused: 'codeUnused',
  old_version: 'oldVersion',
}

/** «350 из 366 школ подключены» of the header (Rollout.html). */
export const rolloutVerdict = (summary: RolloutSummary | undefined): string => {
  if (summary === undefined) return ROLLOUT_LABELS.progress
  const total = summary.schoolsCount
  return ROLLOUT_LABELS.verdict(
    formatNumber(summary.schoolsConnectedCount, 0),
    formatNumber(total, 0),
    plural(total, SCHOOL_COUNT_FORMS),
  )
}

/** Four cells of «Ход внедрения»: connected, alive, silent, not connected (DESIGN.md §3.30). */
export const rolloutKpiItems = (summary: RolloutSummary): KpiStripItem[] => [
  {
    key: 'connected',
    label: ROLLOUT_KPI_LABELS.connected,
    value: formatNumber(summary.schoolsConnectedCount, 0),
    hint: `${formatPercent(summary.connectedPct, 0)} · ${ROLLOUT_LABELS.registry(formatNumber(summary.schoolsTotalCount, 0))}`,
  },
  {
    key: 'alive',
    label: ROLLOUT_KPI_LABELS.alive,
    value: formatNumber(summary.devicesAliveCount, 0),
    hint: `${ROLLOUT_LABELS.registry(formatNumber(summary.devicesCount, 0))}`,
  },
  {
    key: 'silent',
    label: ROLLOUT_KPI_LABELS.silent,
    value: formatNumber(summary.lists.silent, 0),
    hint: ROLLOUT_LABELS.silentWindow(
      formatNumber(summary.silentDays, 0),
      plural(summary.silentDays, ROLLOUT_LABELS.dayForms),
    ),
    alert: summary.lists.silent > 0,
  },
  {
    key: 'not-connected',
    label: ROLLOUT_KPI_LABELS.notConnected,
    value: formatNumber(summary.lists.notConnected, 0),
    hint: `${ROLLOUT_KPI_LABELS.oldVersion}: ${formatNumber(summary.devicesOldVersionCount, 0)}`,
    alert: summary.lists.notConnected > 0,
  },
]

/** Why the school is in this list, in words: «последний сигнал 8 дней назад», «код не использован 9 дней». */
export function rolloutReason(item: RolloutSchoolItem, filter: RolloutFilter): string {
  const days = (count: number): [string, string] => [
    formatNumber(count, 0),
    plural(count, ROLLOUT_LABELS.dayForms),
  ]
  if (filter === 'silent') {
    return item.silentDays === null ? ROLLOUT_LABELS.neverSeen : ROLLOUT_LABELS.silentSince(...days(item.silentDays))
  }
  if (filter === 'code_unused') {
    return item.codeAgeDays === null ? ROLLOUT_LABELS.noDevices : ROLLOUT_LABELS.codeAge(...days(item.codeAgeDays))
  }
  if (filter === 'old_version') return item.agentVersions.join(', ') || NO_VALUE
  return item.hasContact ? ROLLOUT_LABELS.noDevices : `${ROLLOUT_LABELS.noDevices} · ${ROLLOUT_LABELS.noContact}`
}

/** «Усть-Каменогорск · последний сигнал 13:47»: the muted line of a row and of a card. */
export const rolloutDescription = (item: RolloutSchoolItem, filter: RolloutFilter): string => {
  const seen = item.lastSeenAt === null ? ROLLOUT_LABELS.neverSeen : formatRelative(item.lastSeenAt)
  return `${item.regionName} · ${filter === 'silent' ? seen : rolloutReason(item, filter)}`
}
