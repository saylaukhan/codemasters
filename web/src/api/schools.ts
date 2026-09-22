// Schools of the panel: the list (T-24) with server-side sorting and pagination, the card (T-25)
// with its computers, lines and contacts; created and changed in the administration (T-34); lines,
// monitoring points and contacts are added and changed from the card (T-35).
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type {
  LineCreate,
  LineUpdate,
  MonitoringPointCreate,
  MonitoringPointUpdate,
  SchoolContactCreate,
  SchoolContactUpdate,
  SchoolCreate,
  SchoolUpdate,
} from './types'

type Schemas = components['schemas']

// The card shows every computer, line and contact of a school on one page: a school has a few.
const CARD_PAGE = { page: 1, pageSize: 100 }

export const getSchools = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolListItemPage']>('/schools', { query, signal })

export const getSchool = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolDetail']>(`/schools/${schoolId}`, { signal })

export const createSchool = (body: SchoolCreate) =>
  apiRequest<Schemas['SchoolDetail']>('/schools', { method: 'POST', body })

/** Only the fields present change; `null` clears the address or the point, `isActive: false` deactivates. */
export const updateSchool = (schoolId: number, body: SchoolUpdate) =>
  apiRequest<Schemas['SchoolDetail']>(`/schools/${schoolId}`, { method: 'PATCH', body })

/** Status of every local day of the last `days` for the day strip of the cabinet (T-61). */
export const getSchoolDays = (schoolId: number, days: number, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolDays']>(`/schools/${schoolId}/days`, { query: { days }, signal })

export const getSchoolDevices = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['DeviceListItemPage']>(`/schools/${schoolId}/devices`, { query: CARD_PAGE, signal })

export const getSchoolLines = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['LineDetailPage']>(`/schools/${schoolId}/lines`, { query: CARD_PAGE, signal })

export const getSchoolContacts = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolContactDetailPage']>(`/schools/${schoolId}/contacts`, { query: CARD_PAGE, signal })

export const createSchoolLine = (schoolId: number, body: LineCreate) =>
  apiRequest<Schemas['LineDetail']>(`/schools/${schoolId}/lines`, { method: 'POST', body })

/** `status: 'disabled'` switches the line off; its measurements stay. */
export const updateSchoolLine = (schoolId: number, lineId: number, body: LineUpdate) =>
  apiRequest<Schemas['LineDetail']>(`/schools/${schoolId}/lines/${lineId}`, { method: 'PATCH', body })

export const getSchoolPoints = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['MonitoringPointDetailPage']>(`/schools/${schoolId}/points`, { query: CARD_PAGE, signal })

export const createSchoolPoint = (schoolId: number, body: MonitoringPointCreate) =>
  apiRequest<Schemas['MonitoringPointDetail']>(`/schools/${schoolId}/points`, { method: 'POST', body })

/** A new `lineId` moves the computers of the point to that line. */
export const updateSchoolPoint = (schoolId: number, pointId: number, body: MonitoringPointUpdate) =>
  apiRequest<Schemas['MonitoringPointDetail']>(`/schools/${schoolId}/points/${pointId}`, { method: 'PATCH', body })

export const createSchoolContact = (schoolId: number, body: SchoolContactCreate) =>
  apiRequest<Schemas['SchoolContactDetail']>(`/schools/${schoolId}/contacts`, { method: 'POST', body })

export const updateSchoolContact = (schoolId: number, contactId: number, body: SchoolContactUpdate) =>
  apiRequest<Schemas['SchoolContactDetail']>(`/schools/${schoolId}/contacts/${contactId}`, { method: 'PATCH', body })
