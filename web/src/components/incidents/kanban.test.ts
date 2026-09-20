import { describe, expect, it, vi } from 'vitest'

import type { IncidentListItem, IncidentStatus } from '../../api/types'
import { INCIDENT_STATUS_ORDER } from '../../lib/labels'
import { groupByStatus, initialIncidentView, rememberIncidentView } from './kanban'

const incident = (id: number, status: IncidentStatus): IncidentListItem =>
  ({ id, number: `INC-2026-${String(id).padStart(6, '0')}`, status }) as IncidentListItem

describe('grouping of incidents by columns', () => {
  it('keeps the six columns of ТЗ п. 19 even when they are empty', () => {
    const columns = groupByStatus([])
    expect(columns.map((column) => column.status)).toEqual(INCIDENT_STATUS_ORDER)
    expect(columns.every((column) => column.items.length === 0)).toBe(true)
  })

  it('puts every incident into the column of its status, in the order of the list', () => {
    const columns = groupByStatus([
      incident(1, 'in_progress'),
      incident(2, 'new'),
      incident(3, 'in_progress'),
      incident(4, 'closed'),
    ])
    const byStatus = Object.fromEntries(columns.map((column) => [column.status, column.items.map((item) => item.id)]))
    expect(byStatus).toEqual({
      new: [2],
      sent_to_provider: [],
      in_progress: [1, 3],
      awaiting_info: [],
      resolved: [],
      closed: [4],
    })
  })
})

describe('the chosen view of the section', () => {
  it('starts as the list and comes back from the storage of the browser', () => {
    const store = new Map<string, string>()
    const localStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    }
    vi.stubGlobal('window', { localStorage })

    expect(initialIncidentView()).toBe('list')
    rememberIncidentView('board')
    expect(initialIncidentView()).toBe('board')

    vi.unstubAllGlobals()
  })

  it('falls back to the list when the storage is blocked', () => {
    vi.stubGlobal('window', undefined)
    expect(initialIncidentView()).toBe('list')
    vi.unstubAllGlobals()
  })
})
