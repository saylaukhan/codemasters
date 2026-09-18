// School list of the panel (T-24): GET /api/schools with server-side sorting and pagination.
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export const getSchools = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['SchoolListItemPage']>('/schools', { query, signal })
