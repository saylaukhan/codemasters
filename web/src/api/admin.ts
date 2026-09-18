// References of the administration (T-34): districts and cities, providers, connection types. Nothing is
// deleted: schools and lines refer to them; a PATCH changes only the fields present.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type {
  ConnectionTypeCreate,
  ConnectionTypeUpdate,
  ProviderCreate,
  ProviderUpdate,
  RegionCreate,
  RegionUpdate,
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
