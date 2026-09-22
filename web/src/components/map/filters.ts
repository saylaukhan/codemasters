// Filters of the overview and the map (DESIGN.md §2.6, §3.9). They live in the URL under the names
// of the API parameters, so a link opens the same view and one panel drives both the KPIs and the map.
import type { QueryValue } from '../../api/client'
import type { MapFilterOptions, SchoolStatus } from '../../api/types'
import { formatDate } from '../../lib/format'
import { MAP_FILTER_LABELS, SCHOOL_STATUS_LABELS } from '../../lib/labels'

export interface MapFilters {
  regionId?: number
  providerId?: number
  connectionTypeId?: number
  status: SchoolStatus[]
  /** RFC 3339; empty — the default period of the endpoint. */
  periodFrom?: string
  /** RFC 3339; empty — now. */
  periodTo?: string
}

export const NO_FILTERS: MapFilters = { status: [] }

const SCHOOL_STATUSES = Object.keys(SCHOOL_STATUS_LABELS) as SchoolStatus[]

const ID_PARAMS = {
  regionId: 'region_id',
  providerId: 'provider_id',
  connectionTypeId: 'connection_type_id',
} as const

const PERIOD_PARAMS = { periodFrom: 'period_from', periodTo: 'period_to' } as const

const STATUS_PARAM = 'status'

const readId = (value: string | null): number | undefined => {
  const id = Number(value ?? undefined)
  return Number.isInteger(id) && id > 0 ? id : undefined
}

const readMoment = (value: string | null): string | undefined =>
  value && !Number.isNaN(Date.parse(value)) ? value : undefined

const isSchoolStatus = (value: string): value is SchoolStatus => (SCHOOL_STATUSES as string[]).includes(value)

/** Filters from the query string; values the API would reject are dropped, not sent. */
export function readFilters(params: URLSearchParams): MapFilters {
  const filters: MapFilters = { status: [...new Set(params.getAll(STATUS_PARAM).filter(isSchoolStatus))] }
  for (const [key, name] of Object.entries(ID_PARAMS) as [keyof typeof ID_PARAMS, string][]) {
    filters[key] = readId(params.get(name))
  }
  for (const [key, name] of Object.entries(PERIOD_PARAMS) as [keyof typeof PERIOD_PARAMS, string][]) {
    filters[key] = readMoment(params.get(name))
  }
  return filters
}

/** Query string with `filters` in place of the old ones; other parameters of the page stay. */
export function writeFilters(filters: MapFilters, current: URLSearchParams = new URLSearchParams()): URLSearchParams {
  const next = new URLSearchParams(current)
  for (const name of [...Object.values(ID_PARAMS), ...Object.values(PERIOD_PARAMS), STATUS_PARAM]) {
    next.delete(name)
  }
  for (const [key, name] of Object.entries(ID_PARAMS) as [keyof typeof ID_PARAMS, string][]) {
    const id = filters[key]
    if (id !== undefined) next.set(name, String(id))
  }
  for (const [key, name] of Object.entries(PERIOD_PARAMS) as [keyof typeof PERIOD_PARAMS, string][]) {
    const moment = filters[key]
    if (moment) next.set(name, moment)
  }
  for (const status of filters.status) next.append(STATUS_PARAM, status)
  return next
}

export const isFiltered = (filters: MapFilters): boolean =>
  filters.status.length > 0 ||
  [filters.regionId, filters.providerId, filters.connectionTypeId, filters.periodFrom, filters.periodTo].some(
    (value) => value !== undefined,
  )

/** Dimensions that are set: the number of the «Фильтры · N» button of DESIGN.md §9.3. */
export const countFilters = (filters: MapFilters): number =>
  [filters.regionId, filters.providerId, filters.connectionTypeId].filter((id) => id !== undefined).length +
  (filters.status.length > 0 ? 1 : 0) +
  (filters.periodFrom !== undefined || filters.periodTo !== undefined ? 1 : 0)

const nameOf = (options: readonly { id: number; name: string }[] | undefined, id: number): string =>
  options?.find((option) => option.id === id)?.name ?? String(id)

/**
 * Active values listed under the button of the sheet (DESIGN.md §9.3): «Район: Усть-Каменогорск».
 * The analytics has the same three dimensions and a period but no statuses, so they are optional.
 */
export function filterSummary(
  filters: Omit<MapFilters, 'status'> & { status?: readonly SchoolStatus[] },
  options: MapFilterOptions | undefined,
): string[] {
  const parts: string[] = []
  if (filters.regionId !== undefined) {
    parts.push(`${MAP_FILTER_LABELS.region}: ${nameOf(options?.regions, filters.regionId)}`)
  }
  if (filters.providerId !== undefined) {
    parts.push(`${MAP_FILTER_LABELS.provider}: ${nameOf(options?.providers, filters.providerId)}`)
  }
  if (filters.connectionTypeId !== undefined) {
    parts.push(`${MAP_FILTER_LABELS.connectionType}: ${nameOf(options?.connectionTypes, filters.connectionTypeId)}`)
  }
  if (filters.status && filters.status.length > 0) {
    parts.push(`${MAP_FILTER_LABELS.status}: ${filters.status.map((status) => SCHOOL_STATUS_LABELS[status]).join(', ')}`)
  }
  if (filters.periodFrom !== undefined) {
    const until = filters.periodTo === undefined ? '' : ` — ${formatDate(filters.periodTo)}`
    parts.push(`${MAP_FILTER_LABELS.period}: ${formatDate(filters.periodFrom)}${until}`)
  }
  return parts
}

/** Query of GET /api/dashboard/summary and GET /api/map/schools; the client turns keys to snake_case. */
export const filtersQuery = (filters: MapFilters): Record<string, QueryValue> => ({
  regionId: filters.regionId,
  providerId: filters.providerId,
  connectionTypeId: filters.connectionTypeId,
  status: filters.status,
  periodFrom: filters.periodFrom,
  periodTo: filters.periodTo,
})
