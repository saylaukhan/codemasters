// Draft of the export constructor (DESIGN.md §3.24) and the body of POST /api/exports it becomes.
import type { Dayjs } from 'dayjs'

import type {
  ExportAggregateColumn,
  ExportColumn,
  ExportCreate,
  ExportFormat,
  ExportMode,
  QualityStatus,
} from '../../api/types'
import { EXPORT_AGGREGATE_COLUMN_LABELS, EXPORT_COLUMN_LABELS } from '../../lib/labels'

/** Every column in the order of the file. */
export const ALL_COLUMNS = Object.keys(EXPORT_COLUMN_LABELS) as ExportColumn[]

/** Minimum of ТЗ п. 9: always in the file, the API refuses a request without them (invariant 16). */
export const MIN_COLUMNS: readonly ExportColumn[] = ALL_COLUMNS.slice(0, 11)

/** Columns of the aggregates: fixed, one row per school (ТЗ п. 9, T-31). */
export const AGGREGATE_COLUMNS = Object.keys(EXPORT_AGGREGATE_COLUMN_LABELS) as ExportAggregateColumn[]

/** Formats of raw measurements and of the aggregates; PDF is the report of a school (T-32). */
export const RAW_FORMATS: readonly ExportFormat[] = ['xlsx', 'csv', 'json']

export interface ExportDraft {
  /** Raw measurements or the aggregates; the PDF report is T-32. */
  mode: Exclude<ExportMode, 'school_report'>
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

/**
 * Body of POST /api/exports: whole days, the end of the period exclusive. Computers, statuses and
 * columns are raw only: the API refuses them with the aggregates.
 */
export const exportBody = (draft: ExportDraft): ExportCreate => {
  const common = {
    format: draft.format,
    periodFrom: draft.days[0].startOf('day').toISOString(),
    periodTo: draft.days[1].add(1, 'day').startOf('day').toISOString(),
    schoolIds: draft.schoolId === undefined ? [] : [draft.schoolId],
  }
  if (draft.mode === 'aggregates') return { mode: 'aggregates', ...common }
  return {
    mode: 'raw',
    ...common,
    deviceIds: draft.schoolId === undefined ? [] : draft.deviceIds,
    statuses: draft.statuses,
    columns: orderedColumns(draft.columns),
  }
}
