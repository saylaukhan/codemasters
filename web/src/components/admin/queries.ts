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
import {
  createSchool,
  createSchoolContact,
  createSchoolLine,
  createSchoolPoint,
  getSchool,
  getSchools,
  updateSchool,
  updateSchoolContact,
  updateSchoolLine,
  updateSchoolPoint,
} from '../../api/schools'
import type {
  LineCreate,
  LineUpdate,
  MonitoringPointCreate,
  MonitoringPointUpdate,
  SchoolContactCreate,
  SchoolContactUpdate,
} from '../../api/types'
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

// Districts and cities, providers and connection types of VKO fit on one page of the API (at most 100):
// the selects of the forms search among them.
const OPTIONS_PAGE = { page: 1, pageSize: 100 }

const byName = (page: { items: { id: number; name: string }[] }) =>
  [...page.items]
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
    .map((item) => ({ value: item.id, label: item.name }))

/** Districts and cities for the select of the school form, by name. */
export const useRegionOptions = () =>
  useQuery({
    queryKey: ['admin', 'regions', 'options'],
    queryFn: ({ signal }) => getRegions(OPTIONS_PAGE, signal),
    select: byName,
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

/** Providers for the select of the line form, by name. */
export const useProviderOptions = () =>
  useQuery({
    queryKey: ['admin', 'providers', 'options'],
    queryFn: ({ signal }) => getProviders(OPTIONS_PAGE, signal),
    select: byName,
  })

/** Connection types for the select of the line form, by name. */
export const useConnectionTypeOptions = () =>
  useQuery({
    queryKey: ['admin', 'connection-types', 'options'],
    queryFn: ({ signal }) => getConnectionTypes(OPTIONS_PAGE, signal),
    select: byName,
  })

// Lines, points and contacts of a school (T-35): saved from its card, shown in the card, the list and the map.
export const useSaveLine = (schoolId: number) =>
  useSave(
    (body: LineCreate) => createSchoolLine(schoolId, body),
    (lineId: number, body: LineUpdate) => updateSchoolLine(schoolId, lineId, body),
  )

export const useSavePoint = (schoolId: number) =>
  useSave(
    (body: MonitoringPointCreate) => createSchoolPoint(schoolId, body),
    (pointId: number, body: MonitoringPointUpdate) => updateSchoolPoint(schoolId, pointId, body),
  )

export const useSaveContact = (schoolId: number) =>
  useSave(
    (body: SchoolContactCreate) => createSchoolContact(schoolId, body),
    (contactId: number, body: SchoolContactUpdate) => updateSchoolContact(schoolId, contactId, body),
  )
