import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import {
  createConnectionType,
  createProvider,
  createRegion,
  getConnectionTypes,
  getProviders,
  getRegions,
  updateConnectionType,
  updateProvider,
  updateRegion,
} from '../../api/admin'
import { createSchool, getSchool, getSchools, updateSchool } from '../../api/schools'
import type { AdminListView } from './useAdminListView'

// Names of schools and references are shown across the panel: lists, cards, the map and its filters, KPIs, analytics.
const SHOWN_ELSEWHERE = [['admin'], ['schools'], ['map'], ['dashboard'], ['analytics']]

const invalidateShown = (queryClient: QueryClient) =>
  Promise.all(SHOWN_ELSEWHERE.map((queryKey) => queryClient.invalidateQueries({ queryKey })))

/** Query of a list: the search is trimmed, a blank one is not sent. */
const listQuery = ({ q, page, pageSize }: AdminListView) => ({ q: q.trim() || undefined, page, pageSize })

/** Save of a drawer: without `id` — POST of a new record, with it — PATCH of the changed fields. */
export type Save<C, U> = { id?: undefined; body: C } | { id: number; body: U }

function useSave<C, U, R>(create: (body: C) => Promise<R>, update: (id: number, body: U) => Promise<R>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (save: Save<C, U>) => (save.id === undefined ? create(save.body) : update(save.id, save.body)),
    onSuccess: () => invalidateShown(queryClient),
  })
}

/** Schools of the scope, disabled ones included unless filtered (GET /api/schools). */
export const useAdminSchools = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'schools', view],
    queryFn: ({ signal }) => getSchools({ ...listQuery(view), isActive: view.isActive }, signal),
    placeholderData: keepPreviousData,
  })

/** The school being edited: the list has neither its address nor its point. Shares the cache of the card. */
export const useSchoolToEdit = (schoolId: number | undefined) =>
  useQuery({
    queryKey: ['schools', schoolId],
    queryFn: ({ signal }) => getSchool(schoolId as number, signal),
    enabled: schoolId !== undefined,
  })

export const useSaveSchool = () => useSave(createSchool, updateSchool)

export const useRegions = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'regions', view],
    queryFn: ({ signal }) => getRegions(listQuery(view), signal),
    placeholderData: keepPreviousData,
  })

// Districts and cities of VKO fit on one page of the API (at most 100): the select of a school searches among them.
const REGION_OPTIONS = { page: 1, pageSize: 100 }

/** Districts and cities for the select of the school form, by name. */
export const useRegionOptions = () =>
  useQuery({
    queryKey: ['admin', 'regions', 'options'],
    queryFn: ({ signal }) => getRegions(REGION_OPTIONS, signal),
    select: (page) =>
      [...page.items]
        .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
        .map((region) => ({ value: region.id, label: region.name })),
  })

export const useSaveRegion = () => useSave(createRegion, updateRegion)

export const useProviders = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'providers', view],
    queryFn: ({ signal }) => getProviders(listQuery(view), signal),
    placeholderData: keepPreviousData,
  })

export const useSaveProvider = () => useSave(createProvider, updateProvider)

export const useConnectionTypes = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'connection-types', view],
    queryFn: ({ signal }) => getConnectionTypes(listQuery(view), signal),
    placeholderData: keepPreviousData,
  })

export const useSaveConnectionType = () => useSave(createConnectionType, updateConnectionType)
