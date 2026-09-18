// References of the administration (T-34): districts and cities, providers, connection types; threshold
// profiles, schedules and settings (T-37); users (T-38). Nothing is deleted: schools and lines refer to the
// references, a profile or a schedule is switched off, a user is blocked; a PATCH changes only the fields present.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type {
  ConnectionTypeCreate,
  ConnectionTypeUpdate,
  ProviderCreate,
  ProviderUpdate,
  RegionCreate,
  RegionUpdate,
  ScheduleCreate,
  ScheduleUpdate,
  SettingsUpdate,
  ThresholdProfileCreate,
  ThresholdProfileUpdate,
  UserCreate,
  UserUpdate,
} from './types'

type Schemas = components['schemas']

export const getRegions = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['RegionListItemPage']>('/admin/regions', { query, signal })

export const createRegion = (body: RegionCreate) =>
  apiRequest<Schemas['RegionDetail']>('/admin/regions', { method: 'POST', body })

export const updateRegion = (regionId: number, body: RegionUpdate) =>
  apiRequest<Schemas['RegionDetail']>(`/admin/regions/${regionId}`, { method: 'PATCH', body })

export const getProviders = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ProviderDetailPage']>('/admin/providers', { query, signal })

export const createProvider = (body: ProviderCreate) =>
  apiRequest<Schemas['ProviderDetail']>('/admin/providers', { method: 'POST', body })

export const updateProvider = (providerId: number, body: ProviderUpdate) =>
  apiRequest<Schemas['ProviderDetail']>(`/admin/providers/${providerId}`, { method: 'PATCH', body })

export const getConnectionTypes = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ConnectionTypeDetailPage']>('/admin/connection-types', { query, signal })

export const createConnectionType = (body: ConnectionTypeCreate) =>
  apiRequest<Schemas['ConnectionTypeDetail']>('/admin/connection-types', { method: 'POST', body })

export const updateConnectionType = (connectionTypeId: number, body: ConnectionTypeUpdate) =>
  apiRequest<Schemas['ConnectionTypeDetail']>(`/admin/connection-types/${connectionTypeId}`, {
    method: 'PATCH',
    body,
  })

export const getThresholdProfiles = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ThresholdProfileDetailPage']>('/admin/thresholds', { query, signal })

export const createThresholdProfile = (body: ThresholdProfileCreate) =>
  apiRequest<Schemas['ThresholdProfileDetail']>('/admin/thresholds', { method: 'POST', body })

export const updateThresholdProfile = (profileId: number, body: ThresholdProfileUpdate) =>
  apiRequest<Schemas['ThresholdProfileDetail']>(`/admin/thresholds/${profileId}`, { method: 'PATCH', body })

export const getSchedules = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ScheduleDetailPage']>('/admin/schedules', { query, signal })

export const createSchedule = (body: ScheduleCreate) =>
  apiRequest<Schemas['ScheduleDetail']>('/admin/schedules', { method: 'POST', body })

export const updateSchedule = (scheduleId: number, body: ScheduleUpdate) =>
  apiRequest<Schemas['ScheduleDetail']>(`/admin/schedules/${scheduleId}`, { method: 'PATCH', body })

export const getSettings = (signal?: AbortSignal) =>
  apiRequest<Schemas['SettingsDetail']>('/admin/settings', { signal })

export const updateSettings = (body: SettingsUpdate) =>
  apiRequest<Schemas['SettingsDetail']>('/admin/settings', { method: 'PATCH', body })

export const getUsers = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['UserDetailPage']>('/admin/users', { query, signal })

export const createUser = (body: UserCreate) =>
  apiRequest<Schemas['UserDetail']>('/admin/users', { method: 'POST', body })

export const updateUser = (userId: number, body: UserUpdate) =>
  apiRequest<Schemas['UserDetail']>(`/admin/users/${userId}`, { method: 'PATCH', body })
