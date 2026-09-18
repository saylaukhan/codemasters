import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import { schoolReportBody } from './report'

describe('school report request', () => {
  it('asks the PDF of one school for the whole days of the card period', () => {
    const today = dayjs('2026-09-18T15:00:00')

    expect(schoolReportBody(12, 'week', today)).toEqual({
      mode: 'school_report',
      format: 'pdf',
      periodFrom: dayjs('2026-09-12T00:00:00').toISOString(),
      periodTo: dayjs('2026-09-19T00:00:00').toISOString(),
      schoolIds: [12],
    })
    expect(schoolReportBody(12, 'today', today).periodFrom).toBe(dayjs('2026-09-18T00:00:00').toISOString())
    expect(schoolReportBody(12, 'month', today).periodFrom).toBe(dayjs('2026-08-20T00:00:00').toISOString())
  })
})
