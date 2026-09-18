// State of the analytics screen (T-27) in the URL (DESIGN.md §2.6): level, period, filters and the
// two schools being compared, under the names of the API parameters, so a link opens the same view.
import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

import type { QueryValue } from '../../api/client'
import type { AnalyticsLevel, AnalyticsPeriod } from '../../api/types'
import { ANALYTICS_LEVEL_LABELS, PERIOD_LABELS } from '../../lib/labels'

export interface AnalyticsView {
  level: AnalyticsLevel
  period: AnalyticsPeriod
  /** RFC 3339, only with `period: 'custom'`: start inclusive, end exclusive. */
  periodFrom?: string
  periodTo?: string
  regionId?: number
  providerId?: number
  connectionTypeId?: number
  /** Schools of «Сравнение школ», at most two. */
  compare: number[]
}

export const LEVELS = Object.keys(ANALYTICS_LEVEL_LABELS) as AnalyticsLevel[]
export const PRESETS = Object.keys(PERIOD_LABELS) as Exclude<AnalyticsPeriod, 'custom'>[]

export const DEFAULT_VIEW: AnalyticsView = { level: 'school', period: 'week', compare: [] }

const ID_PARAMS = {
  regionId: 'region_id',
  providerId: 'provider_id',
  connectionTypeId: 'connection_type_id',
} as const

const readId = (value: string | null): number | undefined => {
  const id = Number(value ?? undefined)
  return Number.isInteger(id) && id > 0 ? id : undefined
}

const readMoment = (value: string | null): string | undefined =>
  value && !Number.isNaN(Date.parse(value)) ? value : undefined

/** View from the query string; values the API would reject fall back to the defaults. */
export function readView(params: URLSearchParams): AnalyticsView {
  const level = params.get('level') as AnalyticsLevel
  const view: AnalyticsView = {
    ...DEFAULT_VIEW,
    level: LEVELS.includes(level) ? level : DEFAULT_VIEW.level,
    compare: params
      .getAll('compare')
      .map(readId)
      .filter((id): id is number => id !== undefined)
      .slice(0, 2),
  }
  const period = params.get('period') as AnalyticsPeriod
  const periodFrom = readMoment(params.get('period_from'))
  const periodTo = readMoment(params.get('period_to'))
  if (period === 'custom' && periodFrom && periodTo && Date.parse(periodTo) > Date.parse(periodFrom)) {
    Object.assign(view, { period, periodFrom, periodTo })
  } else if ((PRESETS as string[]).includes(period)) {
    view.period = period
  }
  for (const [key, name] of Object.entries(ID_PARAMS) as [keyof typeof ID_PARAMS, string][]) {
    view[key] = readId(params.get(name))
  }
  return view
}

/** Query string of the view; other parameters of the page stay. */
export function writeView(view: AnalyticsView, current: URLSearchParams = new URLSearchParams()): URLSearchParams {
  const next = new URLSearchParams(current)
  for (const name of ['level', 'period', 'period_from', 'period_to', 'compare', ...Object.values(ID_PARAMS)]) {
    next.delete(name)
  }
  next.set('level', view.level)
  next.set('period', view.period)
  if (view.period === 'custom' && view.periodFrom && view.periodTo) {
    next.set('period_from', view.periodFrom)
    next.set('period_to', view.periodTo)
  }
  for (const [key, name] of Object.entries(ID_PARAMS) as [keyof typeof ID_PARAMS, string][]) {
    const id = view[key]
    if (id !== undefined) next.set(name, String(id))
  }
  for (const id of view.compare) next.append('compare', String(id))
  return next
}

export const isFiltered = (view: AnalyticsView): boolean =>
  [view.regionId, view.providerId, view.connectionTypeId].some((id) => id !== undefined)

/** Period part of GET /api/analytics: bounds only with `custom`, otherwise the API answers 422. */
export const periodQuery = (view: AnalyticsView): Record<string, QueryValue> =>
  view.period === 'custom'
    ? { period: view.period, periodFrom: view.periodFrom, periodTo: view.periodTo }
    : { period: view.period }

/** Query of GET /api/analytics for the view; the client turns keys to snake_case. */
export const analyticsQuery = (view: AnalyticsView, level: AnalyticsLevel = view.level): Record<string, QueryValue> => ({
  level,
  ...periodQuery(view),
  regionId: view.regionId,
  providerId: view.providerId,
  connectionTypeId: view.connectionTypeId,
})

export function useAnalyticsView(): [AnalyticsView, (view: AnalyticsView) => void] {
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => readView(params), [params])
  const setView = useCallback(
    (next: AnalyticsView) => setParams((current) => writeView(next, current), { replace: true }),
    [setParams],
  )
  return [view, setView]
}
