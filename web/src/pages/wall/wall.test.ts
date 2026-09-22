import { describe, expect, it } from 'vitest'

import type { NotificationListItem } from '../../api/types'
import { tickerEvents, WALL_TICKER_LIMIT } from './wall'

/** One row of the T-42 stream; only the time and the id matter to the ticker. */
const event = (id: number, createdAt: string): NotificationListItem => ({
  id,
  kind: 'incident_opened',
  title: 'Новый инцидент',
  body: 'Нет соединения',
  incidentId: id,
  incidentNumber: `INC-2026-00000${id}`,
  incidentStatus: 'new',
  schoolId: id,
  schoolName: `Школа № ${id}`,
  readAt: null,
  createdAt,
})

describe('events of the ticker of the wall', () => {
  it('keeps the newest ones first whatever order the page came in', () => {
    const items = [event(1, '2026-09-21T09:15:00Z'), event(2, '2026-09-21T13:41:00Z'), event(3, '2026-09-21T12:58:00Z')]
    expect(tickerEvents(items).map((item) => item.id)).toEqual([2, 3, 1])
  })

  it('drops everything past the limit', () => {
    const items = Array.from({ length: WALL_TICKER_LIMIT + 4 }, (_, index) =>
      event(index, `2026-09-21T10:${String(index).padStart(2, '0')}:00Z`),
    )
    expect(tickerEvents(items)).toHaveLength(WALL_TICKER_LIMIT)
    expect(tickerEvents(items, 2).map((item) => item.id)).toEqual([9, 8])
    expect(tickerEvents(items, 0)).toEqual([])
  })

  it('leaves the page of the API alone', () => {
    const items = [event(1, '2026-09-21T09:15:00Z'), event(2, '2026-09-21T13:41:00Z')]
    tickerEvents(items)
    expect(items.map((item) => item.id)).toEqual([1, 2])
    expect(tickerEvents([])).toEqual([])
  })
})
