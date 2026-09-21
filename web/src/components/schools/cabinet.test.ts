import { describe, expect, it } from 'vitest'

import type { LatestMeasurement, LineDetail, SchoolDay } from '../../api/types'
import { cabinetTiles, cabinetVerdict, daySummary, worstDay } from './cabinet'

const THRESHOLDS = { downloadMinMbps: 20, uploadMinMbps: 20, pingMaxMs: 100, jitterMaxMs: 30, packetLossMaxPct: 2 }

const measurement = (values: Partial<LatestMeasurement> = {}): LatestMeasurement => ({
  measuredAt: '2026-09-21T07:47:00Z',
  connectionStatus: 'online',
  downloadMbps: 45.3,
  uploadMbps: 38.1,
  pingMs: 24,
  jitterMs: 6,
  packetLossPct: 0,
  ifaceType: 'ethernet',
  thresholdsSnapshot: THRESHOLDS,
  qualityStatus: 'normal',
  ...values,
})

const MAIN = { status: 'main', contractDownMbps: 50, contractUpMbps: 50 } as LineDetail

const day = (date: string, status: SchoolDay['status'], downtimeS = 0): SchoolDay => ({
  date,
  status,
  measurementsCount: status === 'no_data' ? 0 : 4,
  problemCount: status === 'normal' ? 0 : 1,
  downtimeS,
})

describe('cabinetVerdict (docs/design/README.md §4.2)', () => {
  it('says the internet is fine while the school is «Норма»', () => {
    expect(cabinetVerdict('normal', measurement(), 50)).toEqual({ key: 'normal' })
  })

  it('names the contract when a speed is under it', () => {
    const slow = measurement({ downloadMbps: 12, qualityStatus: 'critical' })
    expect(cabinetVerdict('critical', slow, 50)).toEqual({ key: 'slowContract' })
  })

  it('says «медленнее, чем положено» when the line has no contract speed', () => {
    const slow = measurement({ downloadMbps: 12, qualityStatus: 'unstable' })
    expect(cabinetVerdict('unstable', slow, null)).toEqual({ key: 'slowNorm' })
  })

  it('reads a breach of the reply or of the losses as interruptions', () => {
    const jumpy = measurement({ pingMs: 180, packetLossPct: 6, qualityStatus: 'unstable' })
    expect(cabinetVerdict('unstable', jumpy, 50)).toEqual({ key: 'unstable' })
  })

  it('tells since when there is no connection, and shortens the phrase without a measurement', () => {
    expect(cabinetVerdict('offline', measurement({ connectionStatus: 'offline' }), 50)).toEqual({
      key: 'offlineSince',
      since: '2026-09-21T07:47:00Z',
    })
    expect(cabinetVerdict('offline', null, 50)).toEqual({ key: 'offline' })
  })

  it('blames the switched-off computer, not the internet, when there is no data', () => {
    expect(cabinetVerdict('no_data', null, 50)).toEqual({ key: 'noData' })
  })
})

describe('daySummary (DESIGN.md §3.27)', () => {
  const DAYS = [
    day('2026-08-23', 'normal'),
    day('2026-09-02', 'offline', 10_800),
    day('2026-09-10', 'unstable'),
    day('2026-09-11', 'critical'),
    day('2026-09-12', 'no_data'),
    day('2026-09-21', 'normal'),
  ]

  it('counts «Нестабильно» and «Критично» together as interruptions', () => {
    expect(daySummary(DAYS)).toEqual({
      normal: 2,
      problem: 2,
      offline: 1,
      noData: 1,
      text: '2 в норме · 2 перебои · 1 без связи · 1 без данных',
    })
  })

  it('leaves out the groups that did not happen', () => {
    expect(daySummary([day('2026-09-20', 'normal'), day('2026-09-21', 'normal')]).text).toBe('2 в норме')
    expect(daySummary([]).text).toBe('')
  })

  it('annotates the worst day, and nothing while every day was «Норма»', () => {
    expect(worstDay(DAYS)).toEqual(DAYS[1])
    expect(worstDay([day('2026-09-21', 'normal')])).toBeUndefined()
  })
})

describe('cabinetTiles (DESIGN.md §3.27)', () => {
  it('gives the speeds both ticks and the reply only the norm one', () => {
    const [download, upload, ping] = cabinetTiles(measurement(), MAIN)

    expect([download.value, download.threshold, download.contract, download.scale]).toEqual([45.3, 20, 50, 60])
    expect([upload.threshold, upload.contract]).toEqual([20, 50])
    expect([ping.value, ping.threshold, ping.contract, ping.scale]).toEqual([24, 100, null, 150])
    expect(ping.higherIsBetter).toBe(false)
  })

  it('colours a tile by its own metric, not by the status of the school', () => {
    const slow = measurement({ downloadMbps: 12, qualityStatus: 'critical' })
    const [download, upload] = cabinetTiles(slow, MAIN)

    expect(download.status).toBe('critical')
    expect(upload.status).toBe('normal')
  })

  it('leaves the tiles «Нет данных» when the computer sent nothing', () => {
    expect(cabinetTiles(null, MAIN).map((tile) => [tile.value, tile.status])).toEqual([
      [null, 'no_data'],
      [null, 'no_data'],
      [null, 'no_data'],
    ])
  })
})
