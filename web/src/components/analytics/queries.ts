import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getAnalytics } from '../../api/analytics'
import type { AnalyticsLevel } from '../../api/types'
import { REFRESH_MS } from '../map/queries'
import { analyticsQuery, periodQuery, type AnalyticsView } from './view'

// Aggregates are refreshed by TimescaleDB every few minutes: polling faster gives nothing new.
const ANALYTICS_REFRESH_MS = 5 * REFRESH_MS

/** Report of a level under the filters of the view (GET /api/analytics, T-27). */
export const useAnalytics = (view: AnalyticsView, level: AnalyticsLevel = view.level) => {
  const query = analyticsQuery(view, level)
  return useQuery({
    queryKey: ['analytics', query],
    queryFn: ({ signal }) => getAnalytics(query, signal),
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
