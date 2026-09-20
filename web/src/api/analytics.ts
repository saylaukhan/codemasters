// Analytics of the panel (T-27): rows of a level, the time series and the hour × weekday heatmap.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export const getAnalytics = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['AnalyticsReport']>('/analytics', { query, signal })

/** Incidents of the same selection: count, length, repeatability (T-45). */
export const getIncidentAnalytics = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['IncidentAnalyticsReport']>('/analytics/incidents', { query, signal })
