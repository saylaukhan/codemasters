import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import {
  createConnectionType,
  createIncidentRule,
  createProvider,
  createRegion,
  createSchedule,
  createThresholdProfile,
  createUser,
  getAuditLog,
  getConnectionTypes,
  getIncidentRules,
  getProviders,
  getRegions,
  getSchedules,
  getSettings,
  getThresholdProfiles,
  getUsers,
  updateConnectionType,
  updateIncidentRule,
  updateProvider,
  updateRegion,
  updateSchedule,
  updateSettings,
  updateThresholdProfile,
  updateUser,
} from '../../api/admin'
import type { QueryValue } from '../../api/client'
import {
  blockDevice,
  createEnrollmentCode,
  getDevices,
  requestTokenRotation,
  unblockDevice,
  updateDevice,
} from '../../api/devices'
import {
  createSchool,
  createSchoolContact,
  createSchoolLine,
  createSchoolPoint,
  getSchool,
  getSchoolLines,
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
  UserCreate,
  UserUpdate,
} from '../../api/types'
import { deviceStatusOf, schoolOption } from './devices'
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

// Devices (T-36): a change shows in the list, the card of the computer, the school card and the counts of the map.
const invalidateDevices = (queryClient: QueryClient) =>
  Promise.all([invalidateShown(queryClient), queryClient.invalidateQueries({ queryKey: ['devices'] })])

/** Computers of the oblast with their school and point, filtered by status (GET /api/devices). */
export const useAdminDevices = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'devices', view],
    queryFn: ({ signal }) => getDevices({ ...listQuery(view), status: deviceStatusOf(view.isActive) }, signal),
    placeholderData: keepPreviousData,
  })

const DEVICE_ACTIONS = { block: blockDevice, unblock: unblockDevice, rotate: requestTokenRotation } as const

export type DeviceAction = keyof typeof DEVICE_ACTIONS

/** Blocking, unblocking or a new token of a device, each after a confirmation. */
export const useDeviceAction = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ action, deviceId }: { action: DeviceAction; deviceId: number }) => DEVICE_ACTIONS[action](deviceId),
    onSuccess: () => invalidateDevices(queryClient),
  })
}

export const useRebindDevice = (deviceId: number) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (monitoringPointId: number) => updateDevice(deviceId, { monitoringPointId }),
    onSuccess: () => invalidateDevices(queryClient),
  })
}

/** Schools for the select of the rebinding form: the first page of the search by School ID or name. */
export const useSchoolOptions = (q: string) =>
  useQuery({
    queryKey: ['admin', 'schools', 'options', q.trim()],
    queryFn: ({ signal }) => getSchools({ q: q.trim() || undefined, page: 1, pageSize: 20 }, signal),
    select: (page) => page.items.map(schoolOption),
    placeholderData: keepPreviousData,
  })

/** One-time installation code of a school: nothing to refresh, the code is shown once. */
export const useIssueEnrollmentCode = () =>
  useMutation({ mutationFn: (schoolId: number) => createEnrollmentCode({ schoolId }) })

// Thresholds, schedules and settings (T-37): statuses of new measurements and of schools follow them.
const pageOnly = ({ page, pageSize }: AdminListView) => ({ page, pageSize })

export const useThresholdProfiles = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'thresholds', view],
    queryFn: ({ signal }) => getThresholdProfiles(pageOnly(view), signal),
    placeholderData: keepPreviousData,
  })

export const useSaveThresholdProfile = () => useSave(createThresholdProfile, updateThresholdProfile)

export const useSchedules = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'schedules', view],
    queryFn: ({ signal }) => getSchedules(pageOnly(view), signal),
    placeholderData: keepPreviousData,
  })

export const useSaveSchedule = () => useSave(createSchedule, updateSchedule)

// Incident rules (T-40): the next detection takes the new values.
export const useIncidentRules = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'incident-rules', view],
    queryFn: ({ signal }) => getIncidentRules(pageOnly(view), signal),
    placeholderData: keepPreviousData,
  })

export const useSaveIncidentRule = () => useSave(createIncidentRule, updateIncidentRule)

export const useSystemSettings = () =>
  useQuery({ queryKey: ['admin', 'settings'], queryFn: ({ signal }) => getSettings(signal) })

export const useSaveSettings = () => {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: updateSettings, onSuccess: () => invalidateShown(queryClient) })
}

/** Lines of the school chosen in the form of a line profile, for its select. */
export const useSchoolLineOptions = (schoolId: number | undefined) =>
  useQuery({
    queryKey: ['schools', schoolId, 'lines'],
    queryFn: ({ signal }) => getSchoolLines(schoolId as number, signal),
    enabled: schoolId !== undefined,
    select: (page) => page.items,
  })

// Users (T-38): only the list of the administration shows them.
export const useUsers = (view: AdminListView) =>
  useQuery({
    queryKey: ['admin', 'users', view],
    queryFn: ({ signal }) => getUsers({ ...listQuery(view), isActive: view.isActive }, signal),
    placeholderData: keepPreviousData,
  })

/** New user, a change of one, a block or an unblock, a new password: each is a POST or a PATCH. */
export const useSaveUser = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (save: Save<UserCreate, UserUpdate>) =>
      save.id === undefined ? createUser(save.body) : updateUser(save.id, save.body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })
}

/** A page of the audit log (T-39); any save of the administration refetches it with the rest of ['admin']. */
export const useAuditLog = (query: Record<string, QueryValue>) =>
  useQuery({
    queryKey: ['admin', 'audit-log', query],
    queryFn: ({ signal }) => getAuditLog(query, signal),
    placeholderData: keepPreviousData,
  })
