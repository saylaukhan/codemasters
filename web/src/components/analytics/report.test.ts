import { describe, expect, it } from 'vitest'

import type { AnalyticsReport, AnalyticsRow } from '../../api/types'
import { compareChart, hoursChart, rankRows, reportTotals } from './report'
import { analyticsQuery, readView, writeView } from './view'

const row = (id: number, problemPct: number | null, availabilityPct: number | null = 100): AnalyticsRow => ({
  id,
  name: `Школа ${id}`,
  measurementsCount: problemPct === null ? 0 : 10,
  problemCount: problemPct === null ? 0 : problemPct / 10,
  problemPct,
  downloadMbps: null,
  uploadMbps: null,
  pingMs: null,
  availabilityPct,
  belowContractPct: null,
  sustainedMismatchLinesCount: null,
})

const REPORT: AnalyticsReport = {
  periodFrom: '2026-09-11T19:00:00Z',
  periodTo: '2026-09-18T19:00:00Z',
  granularity: 'day',
  thresholds: { downloadMinMbps: 20, uploadMinMbps: 20, pingMaxMs: 100, jitterMaxMs: 30, packetLossMaxPct: 2 },
  availabilityMinPct: 99,
  rows: [],
  series: [
    {
      bucketStart: '2026-09-16T19:00:00Z',
      measurementsCount: 3,
      problemCount: 1,
      problemPct: 33.3,
      avgDownloadMbps: 40,
      avgUploadMbps: 20,
      avgPingMs: 10,
    },
    {
      bucketStart: '2026-09-17T19:00:00Z',
      measurementsCount: 1,
      problemCount: 1,
      problemPct: 100,
      avgDownloadMbps: null,
      avgUploadMbps: null,
      avgPingMs: null,
    },
  ],
  heatmap: [
    { weekday: 'mon', hour: 9, measurementsCount: 4, problemCount: 1, problemPct: 25 },
    { weekday: 'tue', hour: 9, measurementsCount: 4, problemCount: 3, problemPct: 75 },
    { weekday: 'mon', hour: 14, measurementsCount: 2, problemCount: 0, problemPct: 0 },
  ],
}

describe('reportTotals', () => {
  it('sums the series and weights the averages by measurements with a value', () => {
    expect(reportTotals(REPORT)).toEqual({
      measurementsCount: 4,
      problemPct: 50,
      avgDownloadMbps: 40,
      avgUploadMbps: 20,
      avgPingMs: 10,
    })
  })

  it('has no values without measurements', () => {
    expect(reportTotals({ ...REPORT, series: [] })).toMatchObject({ measurementsCount: 0, problemPct: null })
  })
})

describe('rankRows', () => {
  it('ranks by the share of problems, then availability; rows without measurements go last', () => {
    const ranked = rankRows([row(1, null), row(2, 20), row(3, 5, 97), row(4, 5, 99.5)])
    expect(ranked.map((item) => [item.id, item.rank])).toEqual([
      [4, 1],
      [3, 2],
      [2, 3],
      [1, null],
    ])
  })
})

describe('hoursChart', () => {
  it('folds the weekdays into 24 hours; hours without measurements are empty', () => {
    const chart = hoursChart(REPORT)
    expect(chart.moments).toHaveLength(24)
    expect(chart.moments[9]).toBe('09:00')
    expect(chart.series[0].values[9]).toBe(50)
    expect(chart.series[0].values[14]).toBe(0)
    expect(chart.series[0].values[3]).toBeNull()
  })
})

describe('compareChart', () => {
  it('puts both schools on the union of their buckets', () => {
    const other = { ...REPORT, series: [{ ...REPORT.series[0], bucketStart: '2026-09-15T19:00:00Z', avgDownloadMbps: 5 }] }
    const chart = compareChart([
      { name: 'A', report: REPORT },
      { name: 'B', report: other },
    ])
    expect(chart.moments).toEqual(['2026-09-15T19:00:00Z', '2026-09-16T19:00:00Z', '2026-09-17T19:00:00Z'])
    expect(chart.series.map((series) => series.name)).toEqual(['Download · A', 'Download · B', 'Ping · A', 'Ping · B'])
    expect(chart.series[0].values).toEqual([null, 40, null])
    expect(chart.series[1].values).toEqual([5, null, null])
  })
})

describe('analytics view', () => {
  it('sends the bounds only with a custom period', () => {
    const custom = readView(
      new URLSearchParams('level=district&period=custom&period_from=2026-09-01T00:00:00Z&period_to=2026-09-08T00:00:00Z'),
    )
    expect(analyticsQuery(custom)).toMatchObject({ level: 'district', period: 'custom', periodTo: '2026-09-08T00:00:00Z' })
    const preset = readView(new URLSearchParams('period=today&period_from=2026-09-01T00:00:00Z&region_id=3'))
    expect(analyticsQuery(preset)).toEqual({
      level: 'school',
      period: 'today',
      regionId: 3,
      providerId: undefined,
      connectionTypeId: undefined,
    })
  })

  it('falls back to a week when the custom bounds are broken and keeps two schools to compare', () => {
    const view = readView(new URLSearchParams('level=nope&period=custom&period_from=2026-09-08&compare=4&compare=x&compare=5&compare=6'))
    expect(view).toMatchObject({ level: 'school', period: 'week', compare: [4, 5] })
    expect(writeView(view, new URLSearchParams('tab=1')).toString()).toBe('tab=1&level=school&period=week&compare=4&compare=5')
  })
})
