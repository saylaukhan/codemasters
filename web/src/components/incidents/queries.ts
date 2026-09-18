import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { ApiError } from '../../api/client'
import {
  changeIncidentStatus,
  createIncident,
  createIncidentComment,
  getIncident,
  getIncidents,
  getSchoolIncidents,
  updateIncident,
} from '../../api/incidents'
import type { IncidentStatusChange, IncidentUpdate } from '../../api/types'
import { REFRESH_MS } from '../map/queries'
import { incidentListQuery, type IncidentListView } from './incidents'

// An incident outside the scope answers 404: asking again will not change that.
const retryUnlessMissing = (count: number, error: Error) =>
  !(error instanceof ApiError && error.status === 404) && count < 3

// Every list and card of incidents lives under ['incidents']; the KPIs of the overview count the open ones.
const invalidateIncidents = (queryClient: QueryClient) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: ['incidents'] }),
    queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
  ])

export const useIncidents = (view: IncidentListView) =>
  useQuery({
    queryKey: ['incidents', 'list', view],
    queryFn: ({ signal }) => getIncidents(incidentListQuery(view), signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })

export const useIncident = (incidentId: number) =>
  useQuery({
    queryKey: ['incidents', incidentId],
    queryFn: ({ signal }) => getIncident(incidentId, signal),
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

/** Incidents of the school card, newest first (GET /api/schools/{id}/incidents). */
export const useSchoolIncidents = (schoolId: number, page: number, pageSize: number) =>
  useQuery({
    queryKey: ['incidents', 'school', schoolId, page, pageSize],
    queryFn: ({ signal }) => getSchoolIncidents(schoolId, { page, pageSize }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

export const useCreateIncident = () => {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: createIncident, onSuccess: () => invalidateIncidents(queryClient) })
}

export const useChangeIncidentStatus = (incidentId: number) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: IncidentStatusChange) => changeIncidentStatus(incidentId, body),
    onSuccess: () => invalidateIncidents(queryClient),
  })
}

export const useUpdateIncident = (incidentId: number) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: IncidentUpdate) => updateIncident(incidentId, body),
    onSuccess: () => invalidateIncidents(queryClient),
  })
}

export const useCommentIncident = (incidentId: number) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (comment: string) => createIncidentComment(incidentId, { comment }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['incidents', incidentId] }),
  })
}
