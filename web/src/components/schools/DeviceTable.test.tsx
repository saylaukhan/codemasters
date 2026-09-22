import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { DeviceListItem } from '../../api/types'
import { DEVICE_STATUS_LABELS, NO_DATA_BLOCKED_HINT, NO_DATA_HINT } from '../../lib/labels'
import { DeviceTable } from './DeviceTable'

const DEVICE: DeviceListItem = {
  id: 8,
  deviceUid: '562e6e9beecd51e718011a04fcbf6b64',
  hostname: 'VigesFedora',
  monitoringPointId: 3,
  monitoringPointName: 'Кабинет информатики',
  room: null,
  lineId: 1,
  lineStatus: 'main',
  agentVersion: 'dev',
  lastSeenAt: '2026-09-22T07:47:00Z',
  status: 'active',
  updateChannel: 'stable',
  currentStatus: 'no_data',
  latestMeasurement: null,
}

const html = (item: DeviceListItem) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <DeviceTable items={[item]} />
    </MemoryRouter>,
  )

describe('DeviceTable (ТЗ п. 4)', () => {
  it('names the column «Качество», so «Активно» of the administration is not its opposite', () => {
    const markup = html(DEVICE)
    expect(markup).toContain('>Качество<')
    expect(markup).not.toContain('>Статус<')
  })

  it('says why there is no data instead of leaving the pill alone (DESIGN.md §4.1)', () => {
    expect(html(DEVICE)).toContain(NO_DATA_HINT)
  })

  it('names blocking as the reason when the server declines the agent (ADR-005)', () => {
    const markup = html({ ...DEVICE, status: 'blocked' })
    expect(markup).toContain(NO_DATA_BLOCKED_HINT)
    expect(markup).not.toContain(NO_DATA_HINT)
  })

  it('leaves a measured computer without a hint', () => {
    const markup = html({ ...DEVICE, currentStatus: 'normal' })
    expect(markup).toContain('Норма')
    expect(markup).not.toContain(NO_DATA_HINT)
    expect(markup).not.toContain(DEVICE_STATUS_LABELS.blocked)
  })
})
