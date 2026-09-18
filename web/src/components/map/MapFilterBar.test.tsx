import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { MapFilterOptions } from '../../api/types'
import { NO_FILTERS, filtersQuery, isFiltered, readFilters, writeFilters } from './filters'
import { MapFilterBar } from './MapFilterBar'

const OPTIONS: MapFilterOptions = {
  regions: [{ id: 7, name: 'Усть-Каменогорск' }],
  providers: [{ id: 3, name: 'Казахтелеком' }],
  connectionTypes: [{ id: 2, name: 'Оптика' }],
}

const noop = () => undefined

describe('filters in the URL', () => {
  it('reads the names of the API parameters', () => {
    const filters = readFilters(
      new URLSearchParams('region_id=7&provider_id=3&status=critical&status=offline&period_from=2026-09-01T00:00:00Z'),
    )

    expect(filters).toEqual({
      regionId: 7,
      providerId: 3,
      connectionTypeId: undefined,
      status: ['critical', 'offline'],
      periodFrom: '2026-09-01T00:00:00Z',
      periodTo: undefined,
    })
  })

  it('drops what the API would reject instead of sending it', () => {
    const filters = readFilters(
      new URLSearchParams('region_id=abc&provider_id=-1&status=broken&status=normal&period_to=x'),
    )

    expect(filters).toEqual({ ...NO_FILTERS, status: ['normal'] })
    expect(isFiltered(filters)).toBe(true)
    expect(isFiltered(readFilters(new URLSearchParams('status=broken')))).toBe(false)
  })

  it('writes the filters back and keeps the other parameters of the page', () => {
    const params = writeFilters(
      { regionId: 7, status: ['critical', 'unstable'] },
      new URLSearchParams('provider_id=3&tab=list'),
    )

    expect(params.toString()).toBe('tab=list&region_id=7&status=critical&status=unstable')
    expect(readFilters(params)).toMatchObject({ regionId: 7, providerId: undefined, status: ['critical', 'unstable'] })
  })

  it('sends the same filters to the KPIs and the map', () => {
    expect(filtersQuery({ regionId: 7, status: ['offline'] })).toEqual({
      regionId: 7,
      providerId: undefined,
      connectionTypeId: undefined,
      status: ['offline'],
      periodFrom: undefined,
      periodTo: undefined,
    })
  })
})

describe('MapFilterBar', () => {
  it('shows the active filter with its value and offers a reset', () => {
    const html = renderToStaticMarkup(
      <MapFilterBar filters={{ regionId: 7, status: ['critical', 'offline'] }} options={OPTIONS} onChange={noop} />,
    )

    expect(html).toContain('Район: Усть-Каменогорск')
    expect(html).toContain('Статус:')
    expect(html).toContain('Критично')
    expect(html).toContain('+1')
    expect(html).toContain('Сбросить')
  })

  it('shows only the captions and no reset without filters', () => {
    const html = renderToStaticMarkup(<MapFilterBar filters={NO_FILTERS} options={OPTIONS} onChange={noop} />)

    expect(html).toContain('Район')
    expect(html).toContain('Тип подключения')
    expect(html).not.toContain('Район:')
    expect(html).not.toContain('Сбросить')
  })
})
