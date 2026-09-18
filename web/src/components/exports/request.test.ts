import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import { exportBody, MIN_COLUMNS, orderedColumns } from './request'

describe('export request', () => {
  it('keeps the minimum of ТЗ п. 9 first, in the order of the file', () => {
    expect(MIN_COLUMNS).toEqual([
      'school_name',
      'hostname',
      'room',
      'date',
      'time',
      'download_mbps',
      'upload_mbps',
      'ping_ms',
      'jitter_ms',
      'packet_loss_pct',
      'quality_status',
    ])
    expect(orderedColumns(['external_ip', 'school_code'])).toEqual([...MIN_COLUMNS, 'school_code', 'external_ip'])
  })

  it('turns whole days into a period with an exclusive end and drops computers without a school', () => {
    const days: [dayjs.Dayjs, dayjs.Dayjs] = [dayjs('2026-09-14T15:00:00'), dayjs('2026-09-15T09:00:00')]
    const body = exportBody({ format: 'csv', days, deviceIds: [7], statuses: ['critical'], columns: [] })

    expect(body).toEqual({
      mode: 'raw',
      format: 'csv',
      periodFrom: dayjs('2026-09-14T00:00:00').toISOString(),
      periodTo: dayjs('2026-09-16T00:00:00').toISOString(),
      schoolIds: [],
      deviceIds: [],
      statuses: ['critical'],
      columns: MIN_COLUMNS,
    })
    expect(exportBody({ format: 'xlsx', days, schoolId: 3, deviceIds: [7], statuses: [], columns: [] })).toMatchObject({
      schoolIds: [3],
      deviceIds: [7],
    })
  })
})
