import { describe, expect, it } from 'vitest'

import type { AnalyticsReport, LineDetail } from '../../api/types'
import { chartCsv } from '../ui/chartOption'
import { speedChart } from './speedChart'

const NBSP = ' '

const REPORT: AnalyticsReport = {
  periodFrom: '2026-09-11T19:00:00Z',
  periodTo: '2026-09-18T09:00:00Z',
  granularity: 'day',
  thresholds: { downloadMinMbps: 20, uploadMinMbps: 20, pingMaxMs: 100, jitterMaxMs: 30, packetLossMaxPct: 2 },
  availabilityMinPct: 99,
  rows: [],
  series: [
    {
      // Midnight in Almaty is 19:00 UTC of the day before.
      bucketStart: '2026-09-16T19:00:00Z',
      measurementsCount: 4,
      problemCount: 1,
      problemPct: 25,
      avgDownloadMbps: 45.5,
      avgUploadMbps: 20,
      avgPingMs: 18,
    },
    {
      bucketStart: '2026-09-17T19:00:00Z',
      measurementsCount: 2,
      problemCount: 2,
      problemPct: 100,
      avgDownloadMbps: null,
      avgUploadMbps: null,
      avgPingMs: null,
    },
  ],
  heatmap: [],
}

const MAIN = { status: 'main', contractDownMbps: 50 } as LineDetail

describe('speedChart', () => {
  it('puts speeds on the left axis and ping on the right, one value per bucket', () => {
    const chart = speedChart(REPORT, MAIN)

    expect(chart.step).toBe('day')
    expect(chart.moments).toEqual(['2026-09-16T19:00:00Z', '2026-09-17T19:00:00Z'])
    expect(chart.series.map((series) => [series.name, series.axis, series.values])).toEqual([
      ['Download', 0, [45.5, null]],
      ['Upload', 0, [20, null]],
      ['Ping', 1, [18, null]],
    ])
  })

  it('marks the thresholds of the report and the contract of the main line', () => {
    expect(speedChart(REPORT, MAIN).marks).toEqual([
      { axis: 0, value: 20, label: `Порог 20${NBSP}Мбит/с` },
      { axis: 1, value: 100, label: `Порог 100${NBSP}мс` },
      { axis: 0, value: 50, label: `Договор 50${NBSP}Мбит/с` },
    ])
    expect(speedChart(REPORT, undefined).marks).toHaveLength(2)
  })

  it('exports the same data as CSV with Almaty dates and empty cells for gaps', () => {
    const lines = chartCsv(speedChart(REPORT, MAIN)).split('\r\n')

    expect(lines).toEqual([
      '﻿Время;Download, Мбит/с;Upload, Мбит/с;Ping, мс',
      '17.09.2026;45.5;20;18',
      '18.09.2026;;;',
    ])
  })
})
