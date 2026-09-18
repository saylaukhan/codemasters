import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getDashboardSummary } from '../../api/overview'
import { filtersQuery, type MapFilters } from '../map/filters'
import { REFRESH_MS } from '../map/queries'

export const useDashboardSummary = (filters: MapFilters) =>
  useQuery({
    queryKey: ['dashboard', 'summary', filters],
    queryFn: ({ signal }) => getDashboardSummary(filtersQuery(filters), signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })
