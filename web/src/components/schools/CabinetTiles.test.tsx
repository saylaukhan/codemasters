import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { LatestMeasurement, LineDetail } from '../../api/types'
import { cabinetTiles } from './cabinet'
import { CabinetTiles } from './CabinetTiles'

const LATEST: LatestMeasurement = {
  measuredAt: '2026-09-21T07:47:00Z',
  connectionStatus: 'online',
  downloadMbps: 45.3,
  uploadMbps: 38.1,
  pingMs: 24,
  jitterMs: 6,
  packetLossPct: 0,
  ifaceType: 'ethernet',
  thresholdsSnapshot: { downloadMinMbps: 20, uploadMinMbps: 20, pingMaxMs: 100, jitterMaxMs: 30, packetLossMaxPct: 2 },
  qualityStatus: 'normal',
}

const MAIN = { status: 'main', contractDownMbps: 50, contractUpMbps: 50 } as LineDetail

const html = renderToStaticMarkup(
  <MemoryRouter>
    <CabinetTiles
      tiles={cabinetTiles(LATEST, MAIN)}
      latest={LATEST}
      availabilityPct={99.4}
      measurementsHref="/devices/8"
    />
  </MemoryRouter>,
)

const phoneHtml = renderToStaticMarkup(
  <MemoryRouter>
    <CabinetTiles
      tiles={cabinetTiles(LATEST, MAIN)}
      latest={LATEST}
      availabilityPct={99.4}
      measurementsHref="/devices/8"
      phone
    />
  </MemoryRouter>,
)

describe('CabinetTiles (DESIGN.md §3.27)', () => {
  it('names the three metrics in Russian with their English term', () => {
    expect(html).toContain('Скорость загрузки')
    expect(html).toContain('Скорость отдачи')
    expect(html).toContain('Отклик')
    expect(html).toContain('· Download')
  })

  it('prints the fact with its unit, the reply without a fraction', () => {
    expect(html).toContain('45,3')
    expect(html).toContain('Мбит/с')
    expect(html).toContain('>24<')
    expect(html).toContain('мс')
  })

  it('gives the speeds both ticks and the reply only the norm one', () => {
    expect(html.match(/data-kind="threshold"/g)).toHaveLength(3)
    expect(html.match(/data-kind="contract"/g)).toHaveLength(2)
    expect(html).toContain('норма от 20')
    expect(html).toContain('по договору 50')
    expect(html).toContain('чем меньше, тем лучше')
    expect(html).toContain('норма до 100')
  })

  it('closes the card with the rest of the measurement and the link to the history', () => {
    expect(html).toContain('Дрожание 6')
    expect(html).toContain('потери пакетов 0%')
    expect(html).toContain('доступность за 7 дней')
    expect(html).toContain('99,4%')
    expect(html).toContain('href="/devices/8"')
    expect(html).toContain('Все замеры')
  })

  it('leads the footer of a phone with the availability and shortens the rest (SchoolPhone.html)', () => {
    const footer = phoneHtml.slice(phoneHtml.indexOf('Доступность за 7 дней'))
    expect(footer).toContain('Доступность за 7 дней')
    expect(footer.indexOf('дрожание 6')).toBeGreaterThan(0)
    expect(footer.indexOf('потери 0%')).toBeGreaterThan(footer.indexOf('дрожание 6'))
    expect(phoneHtml).not.toContain('потери пакетов')
  })
})
