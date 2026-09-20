// Appeal to a provider (T-47, ТЗ п. 17, ADR-011): the target of the letter and the period kept in the address of
// the editor, the facts shown next to it. The number, the sending and the PDF are T-48.
import dayjs from 'dayjs'

import type { AppealContext, AppealDraftRequest, CurrentUser, IncidentDetail, IncidentMetric } from '../../api/types'
import { formatDate, formatDateTime, NO_VALUE } from '../../lib/format'

/** Length limits of backend/app/schemas/appeals.py (`AppealCreate`), checked before sending. */
export const SUBJECT_MAX_LENGTH = 255
export const TEXT_MAX_LENGTH = 20000
export const COMMENT_MAX_LENGTH = 2000

/** Permission of backend/app/auth/permissions.py to write to a provider: Школа, Район/город, Область, Администратор. */
export const APPEAL_CREATE_PERMISSION = 'appeals:create'

export const canCreateAppeal = (user: Pick<CurrentUser, 'permissions'> | undefined): boolean =>
  user?.permissions.includes(APPEAL_CREATE_PERMISSION) ?? false

/** Period of an appeal opened from the school card: an incident brings its own (plan.md §8). */
export const DEFAULT_PERIOD_DAYS = 7

/** Appeal about one incident: its period is `started_at` … `restored_at`, or now while the incident goes on. */
export const incidentAppealTarget = (
  incident: Pick<IncidentDetail, 'id' | 'startedAt' | 'restoredAt'>,
  now: Date = new Date(),
): AppealDraftRequest => ({
  incidentId: incident.id,
  periodFrom: incident.startedAt,
  periodTo: incident.restoredAt ?? now.toISOString(),
})

/** Appeal about one line of a school: the last week, the school card knows no period of its own. */
export const schoolAppealTarget = (schoolId: number, lineId: number, now: Date = new Date()): AppealDraftRequest => ({
  schoolId,
  lineId,
  periodFrom: dayjs(now).subtract(DEFAULT_PERIOD_DAYS, 'day').toISOString(),
  periodTo: dayjs(now).toISOString(),
})

/** Address of the editor: the parameters carry the names the API takes (DESIGN.md §2.6, plan.md §10). */
export function appealTargetQuery(target: AppealDraftRequest): URLSearchParams {
  const params = new URLSearchParams()
  if (target.incidentId != null) params.set('incident_id', String(target.incidentId))
  if (target.schoolId != null) params.set('school_id', String(target.schoolId))
  if (target.lineId != null) params.set('line_id', String(target.lineId))
  params.set('period_from', target.periodFrom)
  params.set('period_to', target.periodTo)
  return params
}

const readId = (value: string | null): number | undefined => {
  const id = Number(value ?? undefined)
  return Number.isInteger(id) && id > 0 ? id : undefined
}

const readInstant = (value: string | null): string | undefined => {
  const date = value ? new Date(value) : null
  return date && !Number.isNaN(date.getTime()) ? date.toISOString() : undefined
}

/**
 * Target read back from the address: one incident, or one line of a school, with the period of the problem —
 * the body of POST /api/appeals/draft as it is. `null` — the address names no target and there is nothing to ask
 * the server about; the API checks the same rule again.
 */
export function readAppealTarget(params: URLSearchParams): AppealDraftRequest | null {
  const periodFrom = readInstant(params.get('period_from'))
  const periodTo = readInstant(params.get('period_to'))
  if (!periodFrom || !periodTo || periodFrom >= periodTo) return null
  const incidentId = readId(params.get('incident_id'))
  if (incidentId !== undefined) return { incidentId, periodFrom, periodTo }
  const schoolId = readId(params.get('school_id'))
  const lineId = readId(params.get('line_id'))
  if (schoolId !== undefined && lineId !== undefined) return { schoolId, lineId, periodFrom, periodTo }
  return null
}

/** «12.09.2026 10:00 — 13.09.2026 09:00» in Asia/Almaty: the period of the appeal in its header and its facts. */
export const periodCaption = (from: string, to: string): string => `${formatDateTime(from)} — ${formatDateTime(to)}`

/** «№ 12/2026 от 12.01.2026»; nothing of the contract is filled in — «—» (ТЗ п. 14). */
export function contractCaption(context: Pick<AppealContext, 'contractNumber' | 'contractDate'>): string {
  const number = context.contractNumber ? `№ ${context.contractNumber}` : ''
  const date = context.contractDate ? `от ${formatDate(context.contractDate)}` : ''
  return [number, date].filter(Boolean).join(' ') || NO_VALUE
}

export interface AppealMetricRow {
  metric: IncidentMetric
  /** Average over the period; `null` — the period holds no measurement with a value. */
  value: number | null
  /** The threshold the measurements were judged by, kept next to the fact (ТЗ п. 11, ADR-004). */
  threshold: number
}

/** Averages of the period against the thresholds applied to them: the metrics block of the facts panel. */
export const metricRows = (context: AppealContext): AppealMetricRow[] => [
  { metric: 'download_mbps', value: context.downloadMbps?.avg ?? null, threshold: context.thresholds.downloadMinMbps },
  { metric: 'upload_mbps', value: context.uploadMbps?.avg ?? null, threshold: context.thresholds.uploadMinMbps },
  { metric: 'ping_ms', value: context.pingMs?.avg ?? null, threshold: context.thresholds.pingMaxMs },
  { metric: 'jitter_ms', value: context.jitterMs?.avg ?? null, threshold: context.thresholds.jitterMaxMs },
  {
    metric: 'packet_loss_pct',
    value: context.packetLossPct?.avg ?? null,
    threshold: context.thresholds.packetLossMaxPct,
  },
]

/**
 * Template the editor opens with when no draft arrived at all (network, 500): the letter is written by hand, the
 * same way it is written when the model is off (ADR-011, «Открыто»). A draft that did arrive brings its own text.
 */
export function fallbackDraft(target: AppealDraftRequest): { subject: string; text: string } {
  const period = periodCaption(target.periodFrom, target.periodTo)
  return {
    subject: 'Обращение по качеству интернет-соединения',
    text: [
      'Уважаемые коллеги!',
      '',
      `Просим разобраться с качеством интернет-соединения за период ${period}.`,
      '',
      'Просим сообщить о причинах и сроках устранения.',
    ].join('\n'),
  }
}
