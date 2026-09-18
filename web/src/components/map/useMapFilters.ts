import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

import { readFilters, writeFilters, type MapFilters } from './filters'

/** Filters of the page, kept in its URL (DESIGN.md §2.6). */
export function useMapFilters(): [MapFilters, (filters: MapFilters) => void] {
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => readFilters(params), [params])
  const setFilters = useCallback(
    (next: MapFilters) => setParams((current) => writeFilters(next, current), { replace: true }),
    [setParams],
  )
  return [filters, setFilters]
}
