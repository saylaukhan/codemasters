// Devices of the panel: the card of a computer and its measurement history by pages (T-26); the list of the
// administration, rebinding, blocking, token rotation and installation codes (T-36). The panel never sees a token.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type { DeviceUpdate, EnrollmentCodeCreate } from './types'

type Schemas = components['schemas']

export const getDevices = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['DeviceDetailPage']>('/devices', { query, signal })

export const getDevice = (deviceId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['DeviceDetail']>(`/devices/${deviceId}`, { signal })

export const getDeviceMeasurements = (deviceId: number, query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['MeasurementListItemPage']>(`/devices/${deviceId}/measurements`, { query, signal })

/** Another monitoring point, possibly of another school: new measurements follow it, the old keep theirs. */
export const updateDevice = (deviceId: number, body: DeviceUpdate) =>
  apiRequest<Schemas['DeviceDetail']>(`/devices/${deviceId}`, { method: 'PATCH', body })

/** The agent is refused until unblocked; its history stays. */
export const blockDevice = (deviceId: number) =>
  apiRequest<Schemas['DeviceDetail']>(`/devices/${deviceId}/block`, { method: 'POST' })

export const unblockDevice = (deviceId: number) =>
  apiRequest<Schemas['DeviceDetail']>(`/devices/${deviceId}/unblock`, { method: 'POST' })

/** The agent takes a new token itself on its next config refresh; the old one stops working then. */
export const requestTokenRotation = (deviceId: number) =>
  apiRequest<Schemas['DeviceDetail']>(`/devices/${deviceId}/token-rotation`, { method: 'POST' })

/** One-time code for ENROLL_CODE of the installer: shown once, the server keeps only its hash. */
export const createEnrollmentCode = (body: EnrollmentCodeCreate) =>
  apiRequest<Schemas['EnrollmentCodeIssued']>('/devices/enrollment-codes', { method: 'POST', body })
