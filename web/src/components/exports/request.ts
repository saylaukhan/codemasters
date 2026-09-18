// Draft of the export constructor (DESIGN.md §3.24) and the body of POST /api/exports it becomes.
import type { Dayjs } from 'dayjs'

import type { ExportColumn, ExportCreate, ExportFormat, QualityStatus } from '../../api/types'
import { EXPORT_COLUMN_LABELS } from '../../lib/labels'

/** Every column in the order of the file. */
export const ALL_COLUMNS = Object.keys(EXPORT_COLUMN_LABELS) as ExportColumn[]

/** Minimum of ТЗ п. 9: always in the file, the API refuses a request without them (invariant 16). */
export const MIN_COLUMNS: readonly ExportColumn[] = ALL_COLUMNS.slice(0, 11)

/** Formats of raw measurements; PDF is the report of a school (T-32). */
export const RAW_FORMATS: readonly ExportFormat[] = ['xlsx', 'csv', 'json']

export interface ExportDraft {
  format: ExportFormat
  /** First and last day of the period, both included. */
  days: [Dayjs, Dayjs]
  schoolId?: number
  deviceIds: number[]
  statuses: QualityStatus[]
  columns: ExportColumn[]
}

/** Chosen columns in the order of the file, the minimum always among them. */
export const orderedColumns = (chosen: readonly ExportColumn[]): ExportColumn[] =>
  ALL_COLUMNS.filter((column) => MIN_COLUMNS.includes(column) || chosen.includes(column))

/** Body of POST /api/exports: whole days, the end of the period exclusive. */
export const exportBody = (draft: ExportDraft): ExportCreate => ({
  mode: 'raw',
  format: draft.format,
  periodFrom: draft.days[0].startOf('day').toISOString(),
  periodTo: draft.days[1].add(1, 'day').startOf('day').toISOString(),
  schoolIds: draft.schoolId === undefined ? [] : [draft.schoolId],
  deviceIds: draft.schoolId === undefined ? [] : draft.deviceIds,
  statuses: draft.statuses,
  columns: orderedColumns(draft.columns),
})
