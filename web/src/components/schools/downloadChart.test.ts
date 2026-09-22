import { describe, expect, it } from 'vitest'

import type { AnalyticsReport, LineDetail } from '../../api/types'
import { downloadChart } from './downloadChart'

const NBSP = ' '

const REPORT: AnalyticsReport = {
  periodFrom: '2026-09-14T18:00:00Z',
  periodTo: '2026-09-21T09:00:00Z',
  granularity: 'day',
  thresholds: { downloadMinMbps: 20, uploadMinMbps: 20, pingMaxMs: 100, jitterMaxMs: 30, packetLossMaxPct: 2 },
  availabilityMinPct: 99,
  rows: [],
  series: [
    {
      // Midnight in Almaty is 19:00 UTC of the day before.
      bucketStart: '2026-09-19T19:00:00Z',
      measurementsCount: 4,
      problemCount: 0,
      problemPct: 0,
      avgDownloadMbps: 45.5,
      avgUploadMbps: 38.1,
      avgPingMs: 24,
    },
    {
      bucketStart: '2026-09-20T19:00:00Z',
      measurementsCount: 0,
      problemCount: 0,
      problemPct: 0,
      avgDownloadMbps: null,
      avgUploadMbps: null,
      avgPingMs: null,
    },
  ],
  heatmap: [],
}

const MAIN = { status: 'main', contractDownMbps: 50 } as LineDetail

describe('downloadChart (DESIGN.md §3.27)', () => {
  it('draws the download alone on one axis, unlike the three series of the school card', () => {
    const chart = downloadChart(REPORT, MAIN)

    expect(chart.axes).toHaveLength(1)
    expect(chart.series.map((series) => [series.name, series.axis, series.values])).toEqual([
      ['Download', 0, [45.5, null]],
    ])
    expect(chart.moments).toEqual(['2026-09-19T19:00:00Z', '2026-09-20T19:00:00Z'])
    expect(chart.step).toBe('day')
  })

  it('marks the norm and the contract in the words of the cabinet', () => {
    expect(downloadChart(REPORT, MAIN).marks).toEqual([
      { axis: 0, value: 20, label: `норма 20${NBSP}Мбит/с` },
      { axis: 0, value: 50, label: `договор 50${NBSP}Мбит/с` },
    ])
  })

  it('leaves out the contract mark when the line has no contract speed', () => {
    expect(downloadChart(REPORT, undefined).marks).toHaveLength(1)
  })
})
