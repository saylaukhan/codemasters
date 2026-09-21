import type { UseQueryResult } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { AttentionItem, AttentionPage, DashboardSummary, SchoolStatusCounts } from '../../api/types'
import { NO_FILTERS, readFilters } from '../map/filters'
import { AttentionCard } from './AttentionCard'
import { schoolsWithStatusPath, statusStripItems } from './strips'
import { overviewVerdict } from './verdict'

const summaryOf = (counts: Partial<SchoolStatusCounts>): DashboardSummary =>
  ({
    statusCounts: { normal: 0, unstable: 0, critical: 0, offline: 0, noData: 0, ...counts },
    schoolsCount: 0,
  }) as DashboardSummary

describe('overviewVerdict (DESIGN.md §3.28)', () => {
  it('counts the normal schools against the judged ones', () => {
    const verdict = overviewVerdict(summaryOf({ normal: 312, unstable: 21, critical: 9, offline: 8 }))
    expect(verdict).toBe('312 школ из 350 сегодня в норме')
  })

  it('says so when every school is in norm', () => {
    expect(overviewVerdict(summaryOf({ normal: 350 }))).toBe('Все 350 школ сегодня в норме')
  })

  it('does not divide by zero when the filters select no school', () => {
    expect(overviewVerdict(summaryOf({ noData: 4 }))).toBe('Школ по заданным фильтрам нет')
  })

  it('has a sentence for the loading state, not an empty title', () => {
    expect(overviewVerdict(undefined)).toBe('Собираем данные')
  })
})

describe('status strip links (docs/design/README.md §4.1)', () => {
  it('opens the list of schools filtered by that status, keeping the other filters', () => {
    const filters = { ...NO_FILTERS, regionId: 7, status: ['normal' as const] }
    const href = schoolsWithStatusPath(filters, 'critical')
    const opened = readFilters(new URLSearchParams(href.slice(href.indexOf('?'))))

    expect(opened.status).toEqual(['critical'])
    expect(opened.regionId).toBe(7)
  })

  it('gives the four quality columns their own link, and «Нет данных» none', () => {
    const items = statusStripItems(summaryOf({ normal: 312, unstable: 21, critical: 9, offline: 8 }), NO_FILTERS)

    expect(items.map((item) => item.status)).toEqual(['normal', 'unstable', 'critical', 'offline'])
    expect(items[3].href).toContain('status=offline')
  })
})

const AT = '2026-09-21T07:47:00Z'

const row = (item: Partial<AttentionItem>): AttentionItem =>
  ({
    kind: 'school',
    reason: 'offline',
    severity: 1,
    schoolId: 1,
    schoolCode: 'VKO-UK-001',
    schoolName: 'ОСШ Катон-Карагай',
    regionName: 'Катон-Карагайский район',
    providerName: 'Алтай-Нет',
    status: 'offline',
    incidentId: null,
    incidentNumber: null,
    appealId: null,
    appealNumber: null,
    metric: null,
    since: AT,
    ...item,
  }) as AttentionItem

describe('AttentionCard (DESIGN.md §3.28)', () => {
  const page: AttentionPage = {
    periodTo: AT,
    total: 17,
    items: [
      row({}),
      row({
        kind: 'incident',
        reason: 'incident_unassigned',
        schoolId: 2,
        schoolName: 'СШ им. Абая',
        regionName: 'Зайсанский район',
        providerName: 'Шығыс-Байланыс',
        status: null,
        incidentId: 412,
        incidentNumber: 'INC-000412',
        metric: 'ping_ms',
        since: '2026-09-18T07:00:00Z',
      }),
    ],
  }
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <AttentionCard attention={{ data: page, isPending: false, isError: false } as UseQueryResult<AttentionPage>} />
    </MemoryRouter>,
  )

  it('leads a school row to its card and an incident row to the incident', () => {
    expect(html).toContain('href="/schools/1"')
    expect(html).toContain('href="/incidents/412"')
  })

  it('says the reason in words and the district with the provider', () => {
    expect(html).toContain('Нет связи')
    expect(html).toContain('Катон-Карагайский район · Алтай-Нет')
    expect(html).toContain('Ping')
    expect(html).toContain('без ответственного с 18.09.2026')
  })

  it('counts the rest of the rows the card did not show', () => {
    expect(html).toContain('>17<')
    expect(html).toContain('Ещё 15 школ')
  })
})
