// PDF report of a school (T-32): the body of POST /api/exports for the period of its card.
import dayjs, { type Dayjs } from 'dayjs'

import type { AnalyticsPeriod, ExportCreate } from '../../api/types'

type CardPeriod = Exclude<AnalyticsPeriod, 'custom'>

/** Days before today a period of the card reaches back, as GET /api/analytics counts them. */
const DAYS_BACK: Record<CardPeriod, number> = { today: 0, week: 6, month: 29 }

/** Whole days up to today with an exclusive end, as the export constructor sends them. */
export const schoolReportBody = (schoolId: number, period: CardPeriod, today: Dayjs = dayjs()): ExportCreate => ({
  mode: 'school_report',
  format: 'pdf',
  periodFrom: today.subtract(DAYS_BACK[period], 'day').startOf('day').toISOString(),
  periodTo: today.add(1, 'day').startOf('day').toISOString(),
  schoolIds: [schoolId],
})
