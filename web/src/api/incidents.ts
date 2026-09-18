// Incidents of the panel (T-41, ТЗ п. 19, ADR-007): the list with its filters, the card with the history,
// manual creation from the school card, the responsible and the description, status changes and comments.
// The status changes only with its own endpoint: the API checks the transitions and the role again.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type { IncidentCommentCreate, IncidentCreate, IncidentStatusChange, IncidentUpdate } from './types'

type Schemas = components['schemas']

export const getIncidents = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['IncidentListItemPage']>('/incidents', { query, signal })

export const getIncident = (incidentId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['IncidentDetail']>(`/incidents/${incidentId}`, { signal })

/** A manual incident starts as «Новый»; the school and the provider come from the line. */
export const createIncident = (body: IncidentCreate) =>
  apiRequest<Schemas['IncidentDetail']>('/incidents', { method: 'POST', body })

/** The responsible or the description; `responsibleUserId: null` takes the responsible off. */
export const updateIncident = (incidentId: number, body: IncidentUpdate) =>
  apiRequest<Schemas['IncidentDetail']>(`/incidents/${incidentId}`, { method: 'PATCH', body })

/** A transition outside the table of T-41 answers 409, «Закрыт» by a role that cannot close — 403. */
export const changeIncidentStatus = (incidentId: number, body: IncidentStatusChange) =>
  apiRequest<Schemas['IncidentDetail']>(`/incidents/${incidentId}/status`, { method: 'POST', body })

export const createIncidentComment = (incidentId: number, body: IncidentCommentCreate) =>
  apiRequest<Schemas['IncidentEventDetail']>(`/incidents/${incidentId}/comments`, { method: 'POST', body })

export const getSchoolIncidents = (schoolId: number, query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['IncidentListItemPage']>(`/schools/${schoolId}/incidents`, { query, signal })
