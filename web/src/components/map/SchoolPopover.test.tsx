import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { SchoolMapFeature } from '../../api/types'
import { NO_VALUE } from '../../lib/format'
import { SchoolPopover } from './SchoolPopover'

const NBSP = '\u00a0'

const SCHOOL: SchoolMapFeature = {
  type: 'Feature',
  id: 42,
  geometry: { type: 'Point', coordinates: [82.6286, 49.9483] },
  properties: {
    schoolCode: 'VKO-0042',
    fullName: 'КГУ «Средняя школа № 42»',
    regionName: 'Усть-Каменогорск',
    providerName: 'Казахтелеком',
    connectionTypeName: 'Оптика',
    contractDownMbps: 50,
    contractUpMbps: 20,
    status: 'critical',
    downloadMbps: 18.2,
    uploadMbps: 12.5,
    pingMs: 140,
    // 19:30 UTC on the 12th is 00:30 on the 13th in Almaty.
    lastMeasuredAt: '2026-09-12T19:30:00Z',
    downloadMinMbps: 20,
    uploadMinMbps: 5,
    pingMaxMs: 100,
  },
}

const EMPTY: SchoolMapFeature = {
  type: 'Feature',
  id: 7,
  geometry: null,
  properties: {
    schoolCode: 'VKO-0007',
    fullName: 'Школа без замеров',
    regionName: 'Алтай',
    providerName: null,
    connectionTypeName: null,
    contractDownMbps: null,
    contractUpMbps: null,
    status: 'no_data',
    downloadMbps: null,
    uploadMbps: null,
    pingMs: null,
    lastMeasuredAt: null,
    downloadMinMbps: null,
    uploadMinMbps: null,
    pingMaxMs: null,
  },
}

const render = (school: SchoolMapFeature) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <SchoolPopover school={school} />
    </MemoryRouter>,
  )

/** Caption → value of the key-value table, in the order they are rendered. */
function rows(html: string): [string, string][] {
  return [...html.matchAll(/<dt>([^<]*)<\/dt><dd[^>]*>([^<]*)<\/dd>/g)].map((match) => [match[1], match[2]])
}

describe('SchoolPopover', () => {
  it('shows the fields of ТЗ п. 13 in their order, time in Asia/Almaty', () => {
    const html = render(SCHOOL)

    expect(html).toContain('КГУ «Средняя школа № 42»')
    expect(html).toContain('VKO-0042')
    expect(html).toContain('Критично')
    expect(html.indexOf('VKO-0042')).toBeLessThan(html.indexOf('Критично'))
    expect(rows(html)).toEqual([
      ['Район/город', 'Усть-Каменогорск'],
      ['Поставщик', 'Казахтелеком'],
      ['Тип подключения', 'Оптика'],
      ['Договорная скорость', `50 / 20${NBSP}Мбит/с`],
      ['Download', `18,2 / 50${NBSP}Мбит/с`],
      ['Upload', `12,5 / 20${NBSP}Мбит/с`],
      ['Ping', `140${NBSP}мс`],
      ['Последний замер', '13.09.2026 00:30'],
    ])
  })

  it('marks in red only the values worse than the thresholds', () => {
    const alerts = [...render(SCHOOL).matchAll(/<dt>([^<]*)<\/dt><dd data-alert="true">/g)].map((match) => match[1])

    expect(alerts).toEqual(['Download', 'Ping'])
  })

  it('leads to the card of the school', () => {
    const html = render(SCHOOL)

    expect(html).toContain('href="/schools/42"')
    expect(html).toContain('Открыть карточку')
  })

  it('shows a dash instead of an empty value', () => {
    const html = render(EMPTY)

    expect(html).toContain('Нет данных')
    expect(html).not.toContain('undefined')
    expect(html).not.toContain('null')
    expect(html).not.toContain('data-alert')
    expect(rows(html)).toEqual([
      ['Район/город', 'Алтай'],
      ['Поставщик', NO_VALUE],
      ['Тип подключения', NO_VALUE],
      ['Договорная скорость', NO_VALUE],
      ['Download', NO_VALUE],
      ['Upload', NO_VALUE],
      ['Ping', NO_VALUE],
      ['Последний замер', NO_VALUE],
    ])
  })
})
