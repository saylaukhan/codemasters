// Rules of the school cabinet (T-61, DESIGN.md §3.27, docs/design/README.md §4.2): the verdict of
// the header, the summary of the day strip and the three tiles «факт против порога». Pure, so the
// page only paints what this returns and every branch has a test.
import type {
  AppealListItem,
  IncidentListItem,
  IncidentStatus,
  LatestMeasurement,
  LineDetail,
  SchoolDay,
  SchoolStatus,
  ThresholdValues,
} from '../../api/types'
import { appealCardPath, incidentCardPath } from '../../app/sections'
import { formatDate, formatDuration, MS_UNIT, SPEED_UNIT } from '../../lib/format'
import { CABINET_DAY_LABELS, CABINET_LABELS, CABINET_METRIC_LABELS, type CabinetVerdictKey } from '../../lib/labels'

/** Days of the strip «Последние 30 дней»; the endpoint takes it as a plain number of local days. */
export const CABINET_DAYS = 30

export interface CabinetVerdict {
  key: CabinetVerdictKey
  /** Moment printed after «Интернета нет с»; absent in every other verdict. */
  since?: string
}

/**
 * Which of the two things broke: a speed, or the reply and the losses. Judged by the snapshot this
 * measurement was rated with, never by the contract (ADR-004) — a speed under the contract but over
 * the norm keeps the school «Норма», and the contract only moves the tick of the tile.
 */
function isSlow(latest: LatestMeasurement): boolean {
  const thresholds = latest.thresholdsSnapshot
  const below = (value: number | null, limit: number | undefined) => value != null && limit != null && value < limit
  return below(latest.downloadMbps, thresholds?.downloadMinMbps) || below(latest.uploadMbps, thresholds?.uploadMinMbps)
}

/**
 * Verdict of the header by the status of the school and by what exactly is broken
 * (docs/design/README.md §4.2). A speed breach reads «медленнее», a breach of the reply or of the
 * losses reads «с перебоями», and an unrated measurement falls back to «с перебоями» too: the
 * director is told that something is wrong even when the snapshot cannot say which metric it was.
 */
export function cabinetVerdict(
  status: SchoolStatus,
  latest: LatestMeasurement | null | undefined,
  contractDownMbps: number | null | undefined,
): CabinetVerdict {
  if (status === 'no_data') return { key: 'noData' }
  if (status === 'offline') {
    return latest ? { key: 'offlineSince', since: latest.measuredAt } : { key: 'offline' }
  }
  if (status === 'normal') return { key: 'normal' }
  if (latest && isSlow(latest)) {
    return { key: contractDownMbps == null ? 'slowNorm' : 'slowContract' }
  }
  return { key: 'unstable' }
}

export interface DaySummary {
  normal: number
  /** «Нестабильно» and «Критично» together: for the director both are «перебои». */
  problem: number
  offline: number
  noData: number
  /** «28 в норме · 1 перебои · 1 без связи»: only the groups that happened (DESIGN.md §3.27). */
  text: string
}

/** Counts of the day strip by group, and the summary line right of its title. */
export function daySummary(days: readonly SchoolDay[]): DaySummary {
  const counts = { normal: 0, problem: 0, offline: 0, noData: 0 }
  for (const day of days) {
    if (day.status === 'normal') counts.normal += 1
    else if (day.status === 'offline') counts.offline += 1
    else if (day.status === 'no_data') counts.noData += 1
    else counts.problem += 1
  }
  const text = (Object.keys(CABINET_DAY_LABELS) as (keyof typeof CABINET_DAY_LABELS)[])
    .filter((group) => counts[group] > 0)
    .map((group) => `${counts[group]} ${CABINET_DAY_LABELS[group]}`)
    .join(' · ')
  return { ...counts, text }
}

// From the calmest to the worst: the day the caption under the strip annotates is the worst one.
const DAY_SEVERITY: readonly SchoolStatus[] = ['normal', 'no_data', 'unstable', 'critical', 'offline']

/** Worst day of the strip, latest of the equally bad ones; nothing when every day was «Норма». */
export function worstDay(days: readonly SchoolDay[]): SchoolDay | undefined {
  let worst: SchoolDay | undefined
  for (const day of days) {
    if (day.status === 'normal') continue
    if (!worst || DAY_SEVERITY.indexOf(day.status) >= DAY_SEVERITY.indexOf(worst.status)) worst = day
  }
  return worst
}

export type CabinetTileKey = 'download' | 'upload' | 'ping'

export interface CabinetTile {
  key: CabinetTileKey
  /** Measured value; `null` leaves the track empty and the tile «Нет данных». */
  value: number | null
  /** Right end of the track the value is read against. */
  scale: number
  threshold: number | null
  /** Speeds carry the contract tick, the reply does not (DESIGN.md §3.27). */
  contract: number | null
  status: SchoolStatus
  unit: string
  higherIsBetter: boolean
}

// A speed track ends a fifth above the contract, so the contract tick stands at 83 % of it; without
// a contract three norms give the same room. The reply is read against one and a half of its norm.
const SPEED_SCALE_OVER_CONTRACT = 1.2
const SPEED_SCALE_OVER_THRESHOLD = 3
const PING_SCALE_OVER_THRESHOLD = 1.5

const scaleOf = (value: number | null, ...candidates: (number | null)[]): number => {
  const scale = candidates.find((candidate) => candidate != null && candidate > 0)
  return scale ?? Math.max(value ?? 0, 1) * 1.25
}

/** Colour of the fill: the status this metric alone earns, not the status of the whole school. */
const tileStatus = (
  value: number | null,
  broken: boolean,
  quality: LatestMeasurement['qualityStatus'],
): SchoolStatus => {
  if (value == null) return 'no_data'
  if (!broken) return 'normal'
  return quality === 'critical' ? 'critical' : 'unstable'
}

/**
 * Three tiles of the cabinet: the fact, the norm of the snapshot this measurement was judged by
 * (ADR-004) and the contract speed of the main line (ТЗ п. 14).
 */
export function cabinetTiles(
  latest: LatestMeasurement | null | undefined,
  mainLine: LineDetail | undefined,
): CabinetTile[] {
  const thresholds: ThresholdValues | null = latest?.thresholdsSnapshot ?? null
  const quality = latest?.qualityStatus ?? null
  const speed = (key: CabinetTileKey, value: number | null, threshold: number | null, contract: number | null) => {
    return {
      key,
      value,
      scale: scaleOf(
        value,
        contract == null ? null : contract * SPEED_SCALE_OVER_CONTRACT,
        threshold == null ? null : threshold * SPEED_SCALE_OVER_THRESHOLD,
      ),
      threshold,
      contract,
      status: tileStatus(value, threshold != null && value != null && value < threshold, quality),
      unit: SPEED_UNIT,
      higherIsBetter: true,
    }
  }
  const pingThreshold = thresholds?.pingMaxMs ?? null
  const ping = latest?.pingMs ?? null
  return [
    speed('download', latest?.downloadMbps ?? null, thresholds?.downloadMinMbps ?? null, mainLine?.contractDownMbps ?? null),
    speed('upload', latest?.uploadMbps ?? null, thresholds?.uploadMinMbps ?? null, mainLine?.contractUpMbps ?? null),
    {
      key: 'ping',
      value: ping,
      scale: scaleOf(ping, pingThreshold == null ? null : pingThreshold * PING_SCALE_OVER_THRESHOLD),
      threshold: pingThreshold,
      contract: null,
      status: tileStatus(ping, pingThreshold != null && ping != null && ping > pingThreshold, quality),
      unit: MS_UNIT,
      higherIsBetter: false,
    },
  ]
}

/** Phone as a `tel:` link: only the digits and the plus reach the dialler (DESIGN.md §3.27). */
export const telHref = (phone: string): string => `tel:${phone.replace(/[^+\d]/g, '')}`

/** Whether a moment falls on today's local day (ADR-014): «Проверено сегодня в 13:47». */
export const isToday = (value: string, now: Date = new Date()): boolean => formatDate(value) === formatDate(now)

export interface CabinetProblem {
  key: string
  href: string
  /** Colour of the dot of the row: a story that is over reads green, one that goes on reads amber. */
  tone: 'normal' | 'unstable'
  /** What broke, in words: «Скорость отдачи ниже нормы · с 12.09.2026». */
  title: string
  /** What came of it: the number and the duration, or the number and the day the letter went. */
  meta: string
  status: IncidentStatus
}

/** Rows of «Проблемы и обращения» shown at once; the rest is behind «Вся история» (T-48). */
export const CABINET_PROBLEMS_LIMIT = 5

const isOver = (status: IncidentStatus): boolean => status === 'resolved' || status === 'closed'

/**
 * Problems of the school and the letters it sent about them, newest first (DESIGN.md §3.27). An
 * incident is named by what it was opened on (ТЗ п. 18), an appeal by its own subject; both lead to
 * their card, which the school role may open by address even without the section in its navigation.
 */
export function cabinetProblems(
  incidents: readonly IncidentListItem[],
  appeals: readonly AppealListItem[],
): CabinetProblem[] {
  const tone = (status: IncidentStatus): CabinetProblem['tone'] => (isOver(status) ? 'normal' : 'unstable')
  const fromIncidents = incidents.map((incident) => ({
    at: incident.startedAt,
    problem: {
      key: `incident-${incident.id}`,
      href: incidentCardPath(incident.id),
      tone: tone(incident.status),
      title: `${
        incident.basisMetrics.map((basis) => CABINET_METRIC_LABELS[basis.metric]).join(', ') || CABINET_LABELS.problem
      } · ${CABINET_LABELS.since} ${formatDate(incident.startedAt)}`,
      meta: `${incident.number} · ${
        incident.durationS == null ? CABINET_LABELS.goesOn : formatDuration(incident.durationS)
      }`,
      status: incident.status,
    },
  }))
  const fromAppeals = appeals.map((appeal) => ({
    at: appeal.sentAt,
    problem: {
      key: `appeal-${appeal.id}`,
      href: appealCardPath(appeal.id),
      tone: tone(appeal.status),
      title: appeal.subject,
      meta: `${appeal.number} · ${formatDate(appeal.sentAt)}`,
      status: appeal.status,
    },
  }))
  return [...fromIncidents, ...fromAppeals]
    .sort((left, right) => right.at.localeCompare(left.at))
    .slice(0, CABINET_PROBLEMS_LIMIT)
    .map((row) => row.problem)
}
