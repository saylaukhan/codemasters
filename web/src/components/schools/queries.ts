import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getAnalytics } from '../../api/analytics'
import { ApiError } from '../../api/client'
import { getSchool, getSchoolContacts, getSchoolDevices, getSchoolLines, getSchools } from '../../api/schools'
import type { AnalyticsPeriod, SchoolSort } from '../../api/types'
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

// A school outside the scope answers 404: asking again will not change that.
const retryUnlessMissing = (count: number, error: Error) =>
  !(error instanceof ApiError && error.status === 404) && count < 3

export const useSchool = (schoolId: number) =>
  useQuery({
    queryKey: ['schools', schoolId],
    queryFn: ({ signal }) => getSchool(schoolId, signal),
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

export const useSchoolDevices = (schoolId: number) =>
  useQuery({
    queryKey: ['schools', schoolId, 'devices'],
    queryFn: ({ signal }) => getSchoolDevices(schoolId, signal),
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

export const useSchoolLines = (schoolId: number) =>
  useQuery({
    queryKey: ['schools', schoolId, 'lines'],
    queryFn: ({ signal }) => getSchoolLines(schoolId, signal),
    retry: retryUnlessMissing,
  })

export const useSchoolContacts = (schoolId: number) =>
  useQuery({
    queryKey: ['schools', schoolId, 'contacts'],
    queryFn: ({ signal }) => getSchoolContacts(schoolId, signal),
    retry: retryUnlessMissing,
  })

/** Chart, availability and averages of one school over a period (GET /api/analytics, T-27). */
export const useSchoolAnalytics = (schoolId: number, period: Exclude<AnalyticsPeriod, 'custom'>) =>
  useQuery({
    queryKey: ['analytics', 'school', schoolId, period],
    queryFn: ({ signal }) => getAnalytics({ level: 'school', schoolId, period }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })
