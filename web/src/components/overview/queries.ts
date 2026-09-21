import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getDashboardAttention, getDashboardSummary } from '../../api/overview'
import { filtersQuery, type MapFilters } from '../map/filters'
import { REFRESH_MS } from '../map/queries'

export const useDashboardSummary = (filters: MapFilters) =>
  useQuery({
    queryKey: ['dashboard', 'summary', filters],
    queryFn: ({ signal }) => getDashboardSummary(filtersQuery(filters), signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })

/** How many rows «Требуют внимания» shows; the rest is counted by «Ещё N школ» (§4.1). */
export const ATTENTION_LIMIT = 6

/** The same filters as the summary: the endpoint reads the school ones and `period_to` (T-60). */
export const useDashboardAttention = (filters: MapFilters) =>
  useQuery({
    queryKey: ['dashboard', 'attention', filters],
    queryFn: ({ signal }) => getDashboardAttention({ ...filtersQuery(filters), limit: ATTENTION_LIMIT }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })
