// Data of the map and the overview through TanStack Query (provided by Refine): cached per filters,
// the previous answer stays on screen while the next one loads, so the map is not rebuilt.
import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getMapFilterOptions, getRegionBoundaries, getSchoolMap } from '../../api/overview'
import { filtersQuery, type MapFilters } from './filters'

// Measurements arrive several times a day and heartbeats every few minutes: a minute is fresh enough.
export const REFRESH_MS = 60_000

export const useSchoolMap = (filters: MapFilters) =>
  useQuery({
    queryKey: ['map', 'schools', filters],
    queryFn: ({ signal }) => getSchoolMap(filtersQuery(filters), signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })

export const useRegionBoundaries = () =>
  useQuery({
    queryKey: ['map', 'regions'],
    queryFn: ({ signal }) => getRegionBoundaries(signal),
    staleTime: Infinity,
  })

export const useMapFilterOptions = () =>
  useQuery({
    queryKey: ['map', 'filters'],
    queryFn: ({ signal }) => getMapFilterOptions(signal),
    staleTime: 5 * REFRESH_MS,
  })
