// Schools of the panel: the list (T-24) with server-side sorting and pagination, the card (T-25)
// with its computers, lines and contacts.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

// The card shows every computer, line and contact of a school on one page: a school has a few.
const CARD_PAGE = { page: 1, pageSize: 100 }

export const getSchools = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolListItemPage']>('/schools', { query, signal })

export const getSchool = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolDetail']>(`/schools/${schoolId}`, { signal })

export const getSchoolDevices = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['DeviceListItemPage']>(`/schools/${schoolId}/devices`, { query: CARD_PAGE, signal })

export const getSchoolLines = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['LineDetailPage']>(`/schools/${schoolId}/lines`, { query: CARD_PAGE, signal })

export const getSchoolContacts = (schoolId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolContactDetailPage']>(`/schools/${schoolId}/contacts`, { query: CARD_PAGE, signal })
