import { describe, expect, it } from 'vitest'

import { cardColumns, sortableColumns, tableLayout, visibleColumns } from './responsive-table'

// The school list of T-24 as the scouting of T-62 prioritised it.
const COLUMNS = [
  { key: 'school', priority: 'primary' as const, sorter: () => 0 },
  { key: 'region', priority: 'secondary' as const },
  { key: 'download', priority: 'secondary' as const, sorter: () => 0 },
  { key: 'upload', priority: 'minor' as const },
  { key: 'ping', priority: 'secondary' as const },
  { key: 'measured', priority: 'minor' as const },
  { key: 'status', priority: 'primary' as const, sorter: true },
]

const keys = (columns: { key: string }[]) => columns.map((column) => column.key)

describe('layout of a table by width (DESIGN.md §9.3)', () => {
  it('goes table → scrolling → cards', () => {
    expect(tableLayout(false, false)).toBe('table')
    expect(tableLayout(true, false)).toBe('scroll')
    expect(tableLayout(true, true)).toBe('cards')
  })
})

describe('columns that survive (DESIGN.md §3.12, step 1)', () => {
  it('keeps every column on the plain table', () => {
    expect(keys(visibleColumns(COLUMNS, 'table'))).toHaveLength(COLUMNS.length)
  })

  it('drops the minor ones while the table scrolls inside the card', () => {
    expect(keys(visibleColumns(COLUMNS, 'scroll'))).toEqual(['school', 'region', 'download', 'ping', 'status'])
  })

  it('treats a column without a priority as secondary', () => {
    const plain = [{ key: 'point' }, { key: 'room' }]
    expect(keys(visibleColumns(plain, 'scroll'))).toEqual(['point', 'room'])
    expect(keys(cardColumns(plain))).toEqual(['point', 'room'])
  })
})

describe('a row becomes a card (DESIGN.md §3.12, step 3)', () => {
  it('pairs the secondary columns first, then the minor ones, at most four', () => {
    expect(keys(cardColumns(COLUMNS))).toEqual(['region', 'download', 'ping', 'upload'])
  })

  it('never pairs a primary column: the card head already shows it', () => {
    expect(keys(cardColumns(COLUMNS, 10))).not.toContain('school')
    expect(keys(cardColumns(COLUMNS, 10))).not.toContain('status')
  })

  it('honours a smaller limit', () => {
    expect(keys(cardColumns(COLUMNS, 2))).toEqual(['region', 'download'])
  })
})

describe('sorting of the card list', () => {
  it('offers only the columns with a client comparator', () => {
    expect(keys(sortableColumns(COLUMNS))).toEqual(['school', 'download'])
  })
})
