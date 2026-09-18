// Incidents of the panel (T-41): the view of the list kept in the URL (DESIGN.md §2.6), the values of the basis
// metrics, the duration, the history entries and the body of a manual incident.
import dayjs, { type Dayjs } from 'dayjs'

import type { QueryValue } from '../../api/client'
import type {
  IncidentCreate,
  IncidentEventDetail,
  IncidentListItem,
  IncidentMetric,
  IncidentStatus,
} from '../../api/types'
import { formatDuration, formatMs, formatPercent, formatSpeed, NO_VALUE } from '../../lib/format'
import {
  INCIDENT_EVENT_LABELS,
  INCIDENT_METRIC_LABELS,
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_ORDER,
  SYSTEM_AUTHOR_LABEL,
} from '../../lib/labels'
import { PAGE_SIZES } from '../schools/useSchoolListView'

/** Length limits of backend/app/schemas/incidents.py, checked before sending. */
export const DESCRIPTION_MAX_LENGTH = 2000
export const COMMENT_MAX_LENGTH = 2000

export interface IncidentListView {
  /** Chosen statuses in the order of ТЗ п. 19; none — all of them. */
  statuses: IncidentStatus[]
  /** Number of the incident or its part, as typed. */
  q: string
  /** First and last day of the period by `started_at`, YYYY-MM-DD; none — all time. */
  days?: [string, string]
  page: number
  pageSize: number
}

const DAY = /^\d{4}-\d{2}-\d{2}$/

const readPositive = (value: string | null, fallback: number): number => {
  const number = Number(value ?? undefined)
  return Number.isInteger(number) && number > 0 ? number : fallback
}

const readDays = (from: string | null, to: string | null): [string, string] | undefined =>
  from && to && DAY.test(from) && DAY.test(to) && from <= to ? [from, to] : undefined

export function readIncidentListView(params: URLSearchParams): IncidentListView {
  const pageSize = readPositive(params.get('page_size'), PAGE_SIZES[0])
  const chosen = params.getAll('status')
  return {
    statuses: INCIDENT_STATUS_ORDER.filter((status) => chosen.includes(status)),
    q: params.get('q') ?? '',
    days: readDays(params.get('from'), params.get('to')),
    page: readPositive(params.get('page'), 1),
    pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : PAGE_SIZES[0],
  }
}

export function writeIncidentListView(current: URLSearchParams, view: IncidentListView): URLSearchParams {
  const updated = new URLSearchParams(current)
  for (const key of ['status', 'q', 'from', 'to']) updated.delete(key)
  for (const status of view.statuses) updated.append('status', status)
  if (view.q) updated.set('q', view.q)
  if (view.days) {
    updated.set('from', view.days[0])
    updated.set('to', view.days[1])
  }
  updated.set('page', String(view.page))
  updated.set('page_size', String(view.pageSize))
  return updated
}

/** Query of GET /api/incidents: the period is whole days in the panel's zone, its end exclusive. */
export const incidentListQuery = (view: IncidentListView): Record<string, QueryValue> => ({
  status: view.statuses,
  q: view.q.trim() || undefined,
  periodFrom: view.days && dayjs(view.days[0]).startOf('day').toISOString(),
  periodTo: view.days && dayjs(view.days[1]).add(1, 'day').startOf('day').toISOString(),
  page: view.page,
  pageSize: view.pageSize,
})

export const isFiltered = (view: IncidentListView): boolean =>
  view.statuses.length > 0 || view.q.trim() !== '' || view.days !== undefined

/** «8,4 Мбит/с», «180 мс», «12%»: units follow the metric; «Нет соединения» has no value. */
export function formatMetricValue(metric: IncidentMetric, value: number | null): string {
  switch (metric) {
    case 'download_mbps':
    case 'upload_mbps':
      return formatSpeed(value)
    case 'ping_ms':
    case 'jitter_ms':
      return formatMs(value)
    case 'packet_loss_pct':
      return formatPercent(value)
    case 'no_connection':
      return NO_VALUE
  }
}

/** «Download, Ping»: the basis metrics of an incident in one line. */
export const basisCaption = (metrics: readonly { metric: IncidentMetric }[]): string =>
  metrics.length ? metrics.map(({ metric }) => INCIDENT_METRIC_LABELS[metric]).join(', ') : NO_VALUE

/**
 * Duration of an incident (plan.md §7): `restored_at − started_at` from the API; while the metrics are not
 * restored — the time since the start, marked as going on.
 */
export function durationCaption(
  incident: Pick<IncidentListItem, 'durationS' | 'startedAt'>,
  now: Date = new Date(),
): string {
  if (incident.durationS !== null) return formatDuration(incident.durationS)
  const elapsed = Math.floor((now.getTime() - new Date(incident.startedAt).getTime()) / 1000)
  const value = formatDuration(elapsed)
  return value === NO_VALUE ? NO_VALUE : `идёт ${value}`
}

/** «Статус: Новый → В работе»; the other entries by their kind. */
export function eventCaption(event: Pick<IncidentEventDetail, 'kind' | 'fromStatus' | 'toStatus'>): string {
  const label = INCIDENT_EVENT_LABELS[event.kind]
  if (event.kind !== 'status_change' || !event.toStatus) return label
  const to = INCIDENT_STATUS_LABELS[event.toStatus]
  return event.fromStatus ? `${label}: ${INCIDENT_STATUS_LABELS[event.fromStatus]} → ${to}` : `${label}: ${to}`
}

/** A person by name; an entry without one is the system's: the detection or the automatic closing. */
export const eventAuthor = (event: Pick<IncidentEventDetail, 'authorUserId' | 'authorUserName'>): string =>
  event.authorUserId === null ? SYSTEM_AUTHOR_LABEL : (event.authorUserName ?? NO_VALUE)

export interface IncidentFormValues {
  lineId?: number
  metrics: IncidentMetric[]
  description: string
  /** Start of the problem; none — the moment of creation. */
  startedAt: Dayjs | null
  /** The author becomes the responsible. */
  responsible: boolean
}

export const INCIDENT_FORM_DEFAULTS: Omit<IncidentFormValues, 'lineId'> = {
  metrics: [],
  description: '',
  startedAt: null,
  responsible: false,
}

/** Body of POST /api/incidents; `lineId` is required by the form before it submits. */
export const incidentCreateBody = (values: IncidentFormValues, userId: number | undefined): IncidentCreate => ({
  lineId: values.lineId as number,
  metrics: values.metrics,
  description: values.description.trim(),
  startedAt: values.startedAt ? values.startedAt.toISOString() : null,
  responsibleUserId: values.responsible && userId !== undefined ? userId : null,
})
