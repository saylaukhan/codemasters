import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getAnalytics, getIncidentAnalytics } from '../../api/analytics'
import type { AnalyticsLevel } from '../../api/types'
import { REFRESH_MS } from '../map/queries'
import { analyticsQuery, periodQuery, type AnalyticsView } from './view'

// Aggregates are refreshed by TimescaleDB every few minutes: polling faster gives nothing new.
const ANALYTICS_REFRESH_MS = 5 * REFRESH_MS

/** Report of a level under the filters of the view (GET /api/analytics, T-27); a hidden tab does not poll. */
export const useAnalytics = (view: AnalyticsView, level: AnalyticsLevel = view.level, enabled = true) => {
  const query = analyticsQuery(view, level)
  return useQuery({
    queryKey: ['analytics', query],
    queryFn: ({ signal }) => getAnalytics(query, signal),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: ANALYTICS_REFRESH_MS,
  })
}

/** Incidents of the same selection: count, length, repeatability (GET /api/analytics/incidents, T-45). */
export const useIncidentAnalytics = (view: AnalyticsView, enabled = true) => {
  const query = analyticsQuery(view)
  return useQuery({
    queryKey: ['analytics', 'incidents', query],
    queryFn: ({ signal }) => getIncidentAnalytics(query, signal),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: ANALYTICS_REFRESH_MS,
  })
}

/** Report of one school for «Сравнение школ»: only the period applies, the filters do not. */
export const useSchoolReport = (view: AnalyticsView, schoolId: number | undefined) => {
  const query = { level: 'school', schoolId, ...periodQuery(view) }
  return useQuery({
    queryKey: ['analytics', query],
    queryFn: ({ signal }) => getAnalytics(query, signal),
    enabled: schoolId !== undefined,
    placeholderData: keepPreviousData,
    refetchInterval: ANALYTICS_REFRESH_MS,
  })
}
