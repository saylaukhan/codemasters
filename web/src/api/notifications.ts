// Notifications of the panel (T-42, ТЗ п. 18, DESIGN.md §3.5, §3.23): the bell of the header, its
// counter, «Отметить все как прочитанные» and the stream that keeps both fresh without a page reload.
// The stream is read with `fetch`, not `EventSource`, so the access token travels in the
// Authorization header and never in the URL (ADR-009); its frames are camelized like every payload.
import { camelize, type Camelize } from './case'
import { apiFetch, apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export const getNotifications = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['NotificationListItemPage']>('/notifications', { query, signal })

export const getUnreadCount = (signal?: AbortSignal) =>
  apiRequest<Schemas['NotificationUnreadCount']>('/notifications/unread-count', { signal })

/** Marks every notification of the caller read: there is no per-row endpoint (DESIGN.md §3.23). */
export const readAllNotifications = () => apiRequest<null>('/notifications/read-all', { method: 'POST' })

/** Payload of one `notification` event: the new row and the counter as it stands after it. */
interface NotificationEventPayload {
  notification: Schemas['NotificationListItem']
  unread: number
}

export type NotificationEvent = Camelize<NotificationEventPayload>

// The server sends nothing but `notification`; a comment line («: keepalive») holds the line open.
const EVENT_NAME = 'notification'
const FRAME_SEPARATOR = /\r?\n\r?\n/
const LINE_SEPARATOR = /\r?\n/

/** `field: value` of one SSE line; the single space after the colon belongs to the format. */
function parseLine(line: string): [string, string] {
  const colon = line.indexOf(':')
  if (colon === -1) return [line, '']
  return [line.slice(0, colon), line.slice(colon + 1).replace(/^ /, '')]
}

function parseFrame(frame: string): NotificationEvent | null {
  let name = ''
  const data: string[] = []
  for (const line of frame.split(LINE_SEPARATOR)) {
    // An empty line ends the frame, a line opening with a colon is a comment: neither carries data.
    if (line === '' || line.startsWith(':')) continue
    const [field, value] = parseLine(line)
    if (field === 'event') name = value
    else if (field === 'data') data.push(value)
  }
  if (name !== EVENT_NAME || data.length === 0) return null
  try {
    return camelize<NotificationEventPayload>(JSON.parse(data.join('\n')))
  } catch {
    return null
  }
}

/**
 * Whole frames of the text read so far and the tail that is not a frame yet: a chunk of the stream
 * may cut a frame in half, so the caller keeps `rest` and prepends it to what comes next.
 */
export function parseEventStream(buffer: string): { events: NotificationEvent[]; rest: string } {
  const frames = buffer.split(FRAME_SEPARATOR)
  const rest = frames.pop() ?? ''
  const events: NotificationEvent[] = []
  for (const frame of frames) {
    const event = parseFrame(frame)
    if (event) events.push(event)
  }
  return { events, rest }
}

/**
 * Reads GET /api/notifications/stream until `signal` aborts or the server closes it, calling
 * `onEvent` on every new notification of the caller. Resolving means the stream ended: it is the
 * caller who decides whether to open it again.
 */
export async function streamNotifications(
  onEvent: (event: NotificationEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await apiFetch('/notifications/stream', { accept: 'text/event-stream', signal })
  if (!response.body) return
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    for (;;) {
      const chunk = await reader.read()
      if (chunk.done) return
      const parsed = parseEventStream(buffer + chunk.value)
      buffer = parsed.rest
      parsed.events.forEach(onEvent)
    }
  } finally {
    reader.releaseLock()
  }
}
