import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getSchools } from '../../api/schools'
import type { SchoolSort } from '../../api/types'
import { filtersQuery, type MapFilters } from '../map/filters'
import { REFRESH_MS } from '../map/queries'

export interface SchoolListView {
  sort?: SchoolSort
  page: number
  pageSize: number
}

export const useSchoolList = (filters: MapFilters, view: SchoolListView) =>
  useQuery({
    queryKey: ['schools', 'list', filters, view],
    queryFn: ({ signal }) => getSchools({ ...filtersQuery(filters), ...view }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })
