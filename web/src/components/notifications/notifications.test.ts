import { describe, expect, it } from 'vitest'

import { parseEventStream } from '../../api/notifications'
import { NOTIFICATION_STATUS, notificationListQuery, unreadCaption } from './notifications'

const frame = (id: number, unread: number): string =>
  `event: notification\ndata: ${JSON.stringify({
    notification: {
      id,
      kind: 'incident_opened',
      title: `Новый инцидент INC-2026-00012${id}`,
      body: 'Нет соединения · Школа № 1, основная линия',
      incident_id: 10 + id,
      incident_number: `INC-2026-00012${id}`,
      incident_status: 'new',
      school_id: 1,
      school_name: 'Школа № 1',
      read_at: null,
      created_at: '2026-09-20T05:00:00Z',
    },
    unread,
  })}\n\n`

describe('frames of the notification stream', () => {
  it('reads an event and camelizes its payload', () => {
    const { events, rest } = parseEventStream(frame(1, 3))
    expect(rest).toBe('')
    expect(events).toHaveLength(1)
    expect(events[0].unread).toBe(3)
    expect(events[0].notification).toMatchObject({
      id: 1,
      incidentId: 11,
      incidentNumber: 'INC-2026-000121',
      schoolName: 'Школа № 1',
      readAt: null,
      createdAt: '2026-09-20T05:00:00Z',
    })
  })

  it('skips the keepalive comments and keeps several events of one chunk', () => {
    const { events, rest } = parseEventStream(`: keepalive\n\n${frame(1, 1)}${frame(2, 2)}: keepalive\n\n`)
    expect(events.map((event) => event.notification.id)).toEqual([1, 2])
    expect(rest).toBe('')
  })

  it('holds back a frame cut in half until the rest of it arrives', () => {
    const whole = frame(7, 1)
    const cut = whole.length - 12
    const first = parseEventStream(whole.slice(0, cut))
    expect(first.events).toEqual([])
    const second = parseEventStream(first.rest + whole.slice(cut))
    expect(second.events.map((event) => event.notification.id)).toEqual([7])
    expect(second.rest).toBe('')
  })

  it('drops a frame that is not a notification or not JSON', () => {
    expect(parseEventStream('event: notification\ndata: {\n\n').events).toEqual([])
    expect(parseEventStream('event: other\ndata: {"unread": 1}\n\n').events).toEqual([])
  })
})

describe('panel of the bell', () => {
  it('asks the API for the unread ones only on the second tab', () => {
    expect(notificationListQuery('all').unreadOnly).toBeUndefined()
    expect(notificationListQuery('unread').unreadOnly).toBe(true)
    expect(notificationListQuery('all').pageSize).toBe(20)
  })

  it('shows the counter up to «99+»', () => {
    expect(unreadCaption(1)).toBe('1')
    expect(unreadCaption(99)).toBe('99')
    expect(unreadCaption(100)).toBe('99+')
  })

  it('colours the dot of a row by what happened to the incident', () => {
    expect(NOTIFICATION_STATUS.incident_opened).toBe('critical')
    expect(NOTIFICATION_STATUS.incident_status_changed).toBe('unstable')
    expect(NOTIFICATION_STATUS.incident_restored).toBe('normal')
  })
})
