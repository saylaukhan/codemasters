// Logs of the administration (T-39): «Аудит» — what people did, «События» — rejected agent requests. Both read
// GET /api/admin/audit-log; the filters live in the URL (DESIGN.md §2.6), the period is whole days, its end exclusive.
import dayjs from 'dayjs'

import type { QueryValue } from '../../api/client'
import type { AuditAction } from '../../api/types'
import { AUDIT_BOOLEAN_LABELS, AUDIT_EMPTY_VALUE_LABEL, AUDIT_FIELD_LABELS } from '../../lib/labels'
import { PAGE_SIZES } from '../schools/useSchoolListView'

export type AuditLogKind = 'audit' | 'events'

/** Actions of the tab: sign-ins, changes and exports of people; transfer errors of agents (ТЗ п. 12). */
export const KIND_ACTIONS: Record<AuditLogKind, readonly AuditAction[]> = {
  audit: [
    'login_success',
    'login_failure',
    'create',
    'update',
    'block',
    'unblock',
    'password_reset',
    'status_change',
    'export',
  ],
  events: ['transfer_error'],
}

export interface AuditLogView {
  /** Part of the e-mail or the IP address, as typed. */
  q: string
  /** Chosen actions of the tab; none — all of them. */
  actions: AuditAction[]
  /** First and last day of the period, YYYY-MM-DD; none — all time. */
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

export function readAuditLogView(params: URLSearchParams, kind: AuditLogKind): AuditLogView {
  const pageSize = readPositive(params.get('page_size'), PAGE_SIZES[0])
  return {
    q: params.get('q') ?? '',
    actions: params
      .getAll('action')
      .filter((action): action is AuditAction => KIND_ACTIONS[kind].includes(action as AuditAction)),
    days: readDays(params.get('from'), params.get('to')),
    page: readPositive(params.get('page'), 1),
    pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : PAGE_SIZES[0],
  }
}

export function writeAuditLogView(current: URLSearchParams, view: AuditLogView): URLSearchParams {
  const updated = new URLSearchParams(current)
  for (const key of ['q', 'action', 'from', 'to']) updated.delete(key)
  if (view.q) updated.set('q', view.q)
  for (const action of view.actions) updated.append('action', action)
  if (view.days) {
    updated.set('from', view.days[0])
    updated.set('to', view.days[1])
  }
  updated.set('page', String(view.page))
  updated.set('page_size', String(view.pageSize))
  return updated
}

/** Query of GET /api/admin/audit-log: the actions of the tab unless some are chosen; the search trimmed. */
export const auditLogQuery = (view: AuditLogView, kind: AuditLogKind): Record<string, QueryValue> => ({
  q: view.q.trim() || undefined,
  action: view.actions.length > 0 ? view.actions : KIND_ACTIONS[kind],
  periodFrom: view.days && dayjs(view.days[0]).startOf('day').toISOString(),
  periodTo: view.days && dayjs(view.days[1]).add(1, 'day').startOf('day').toISOString(),
  page: view.page,
  pageSize: view.pageSize,
})

export const isFiltered = (view: AuditLogView): boolean =>
  view.q.trim() !== '' || view.actions.length > 0 || view.days !== undefined

const changeValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return AUDIT_EMPTY_VALUE_LABEL
  if (typeof value === 'boolean') return AUDIT_BOOLEAN_LABELS[value ? 'true' : 'false']
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export interface ChangeLine {
  field: string
  old: string
  new: string
}

/** Changed fields `{field: {old, new}}` of a record as «field: old → new» lines. */
export const changeLines = (changes: Record<string, unknown> | null | undefined): ChangeLine[] =>
  Object.entries(changes ?? {}).map(([field, change]) => {
    const { old, new: next } = (change ?? {}) as { old?: unknown; new?: unknown }
    return { field: AUDIT_FIELD_LABELS[field] ?? field, old: changeValue(old), new: changeValue(next) }
  })
