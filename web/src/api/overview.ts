// Overview and map of the panel (T-22): KPIs, schools as GeoJSON, district boundaries, filter values.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export const getDashboardSummary = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['DashboardSummary']>('/dashboard/summary', { query, signal })

/** Rows that ask for a person (T-60): the endpoint reads the school filters, `period_to` and `limit`. */
export const getDashboardAttention = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['AttentionPage']>('/dashboard/attention', { query, signal })

export const getSchoolMap = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolMapFeatureCollection']>('/map/schools', { query, signal })

export const getRegionBoundaries = (signal?: AbortSignal) =>
  apiRequest<Schemas['RegionMapFeatureCollection']>('/map/regions', { signal })

export const getMapFilterOptions = (signal?: AbortSignal) =>
  apiRequest<Schemas['MapFilterOptions']>('/map/filters', { signal })
