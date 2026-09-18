import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { MeasurementListItem } from '../../api/types'
import { MeasurementTable } from './MeasurementTable'

const MEASUREMENT: MeasurementListItem = {
  measurementUuid: '00000000-0000-0000-0000-000000000001',
  // 19:30 UTC on the 11th is 00:30 on the 12th in Almaty.
  measuredAt: '2026-09-11T19:30:00Z',
  receivedAt: '2026-09-11T19:31:00Z',
  connectionStatus: 'online',
  downloadMbps: 12.5,
  uploadMbps: 30,
  pingMs: 20,
  jitterMs: 3,
  packetLossPct: 0,
  ifaceType: 'ethernet',
  thresholdsSnapshot: {
    downloadMinMbps: 20,
    uploadMinMbps: 10,
    pingMaxMs: 100,
    jitterMaxMs: 30,
    packetLossMaxPct: 2,
  },
  qualityStatus: 'critical',
  lineId: 1,
  durationS: 18,
  externalIp: null,
  server: null,
  agentVersion: '1.2.0',
  contractOk: null,
}

const render = (items: MeasurementListItem[]) =>
  renderToStaticMarkup(
    <MeasurementTable items={items} total={items.length} page={1} pageSize={20} onPageChange={() => {}} />,
  )

describe('MeasurementTable', () => {
  it('shows the time in Almaty and the status from the dictionary', () => {
    const html = render([MEASUREMENT])

    expect(html).toContain('12.09.2026')
    expect(html).toContain('00:30')
    expect(html).toContain('Критично')
    expect(html).not.toContain('Не оценивает линию')
  })

  it('marks a Wi-Fi measurement as not rating the line', () => {
    const html = render([{ ...MEASUREMENT, ifaceType: 'wifi', qualityStatus: null }])

    expect(html).toContain('Wi‑Fi')
    expect(html).toContain('Не оценивает линию')
  })
})
