// Devices of the panel (T-26): the card of a computer and its measurement history by pages.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export const getDevice = (deviceId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['DeviceDetail']>(`/devices/${deviceId}`, { signal })

export const getDeviceMeasurements = (deviceId: number, query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['MeasurementListItemPage']>(`/devices/${deviceId}/measurements`, { query, signal })
