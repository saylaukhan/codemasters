// Notification panel of the header (T-42, DESIGN.md §3.5, §3.23): the query of a tab, the colour of the
// status dot of a row and the counter of the bell. Rows themselves come from the API already formed.
import type { QueryValue } from '../../api/client'
import type { NotificationKind, SchoolStatus } from '../../api/types'
import { NOTIFICATIONS_OVERFLOW_LABEL, type NotificationTabKey } from '../../lib/labels'

// One screen of the panel; older notifications stay behind the scroll of the next page of the API.
export const NOTIFICATION_PAGE_SIZE = 20

// More unread than the counter of the bell can hold: above this it shows «99+».
const COUNTER_MAX = 99

/** Only three of the five statuses of DESIGN.md §4.1 can stand next to a notification. */
type NotificationStatus = Extract<SchoolStatus, 'normal' | 'unstable' | 'critical'>

/**
 * Colour of the dot of a row (DESIGN.md §3.23, §4.1): an incident that has just opened is «Критично»,
 * one whose metrics came back is «Норма», any other move of it is «Нестабильно».
 */
export const NOTIFICATION_STATUS: Record<NotificationKind, NotificationStatus> = {
  incident_opened: 'critical',
  incident_status_changed: 'unstable',
  incident_restored: 'normal',
}

/** Query of GET /api/notifications: the «Непрочитанные» tab is filtered by the API, not by the panel. */
export const notificationListQuery = (tab: NotificationTabKey): Record<string, QueryValue> => ({
  unreadOnly: tab === 'unread' ? true : undefined,
  pageSize: NOTIFICATION_PAGE_SIZE,
})

/** Counter of the bell: «99+» above what fits; at zero the bell carries no counter at all. */
export const unreadCaption = (unread: number): string =>
  unread > COUNTER_MAX ? NOTIFICATIONS_OVERFLOW_LABEL : String(unread)
