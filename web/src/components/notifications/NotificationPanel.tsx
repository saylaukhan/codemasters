import { Tabs } from 'antd'
import { BellOff } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import type { NotificationListItem } from '../../api/types'
import { incidentCardPath } from '../../app/sections'
import { formatRelative } from '../../lib/format'
import {
  NOTIFICATIONS_EMPTY_LABEL,
  NOTIFICATIONS_READ_ALL_LABEL,
  NOTIFICATIONS_TITLE,
  NOTIFICATIONS_UNREAD_EMPTY_LABEL,
  NOTIFICATION_KIND_LABELS,
  NOTIFICATION_TAB_LABELS,
  type NotificationTabKey,
} from '../../lib/labels'
import { Button } from '../ui/Button'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import styles from './Notifications.module.css'
import { NOTIFICATION_STATUS } from './notifications'
import { useNotifications, useReadAllNotifications, useUnreadCount } from './queries'

const TAB_ITEMS = (Object.keys(NOTIFICATION_TAB_LABELS) as NotificationTabKey[]).map((key) => ({
  key,
  label: NOTIFICATION_TAB_LABELS[key],
}))

interface NotificationRowProps {
  notification: NotificationListItem
  /** The panel closes when a row leads to the incident card. */
  onOpen: () => void
}

/** Row of the panel (DESIGN.md §3.23): status dot, title 14/500, school, time; unread on `--bg-subtle`. */
function NotificationRow({ notification, onOpen }: NotificationRowProps) {
  const unread = notification.readAt === null
  return (
    <Link
      to={incidentCardPath(notification.incidentId)}
      className={unread ? `${styles.item} ${styles.unread}` : styles.item}
      onClick={onOpen}
    >
      <span
        className={styles.dot}
        data-status={NOTIFICATION_STATUS[notification.kind]}
        role="img"
        aria-label={NOTIFICATION_KIND_LABELS[notification.kind]}
      />
      <span className={styles.text}>
        <span className={styles.itemTitle}>{notification.title}</span>
        <span className={styles.school}>{notification.schoolName}</span>
        <span className={styles.time}>{formatRelative(notification.createdAt)}</span>
      </span>
    </Link>
  )
}

/** Panel of the bell (DESIGN.md §3.23): 400px, the two tabs and «Отметить все как прочитанные». */
export function NotificationPanel({ onOpenIncident }: { onOpenIncident: () => void }) {
  const [tab, setTab] = useState<NotificationTabKey>('all')
  const notifications = useNotifications(tab)
  const unread = useUnreadCount().data?.unread ?? 0
  const readAll = useReadAllNotifications()

  const items = notifications.data?.items ?? []

  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        <h2 className={styles.title}>{NOTIFICATIONS_TITLE}</h2>
        <Button
          kind="link"
          size="small"
          disabled={unread === 0}
          loading={readAll.isPending}
          onClick={() => readAll.mutate()}
        >
          {NOTIFICATIONS_READ_ALL_LABEL}
        </Button>
      </div>
      <Tabs
        className={styles.tabs}
        activeKey={tab}
        onChange={(key) => setTab(key as NotificationTabKey)}
        items={TAB_ITEMS}
      />
      <div className={styles.list}>
        {notifications.isPending && (
          <div className={styles.state}>
            <ContentSkeleton rows={3} />
          </div>
        )}
        {notifications.isError && (
          <div className={styles.state}>
            <ErrorState error={notifications.error} onRetry={() => void notifications.refetch()} />
          </div>
        )}
        {notifications.isSuccess && items.length === 0 && (
          <div className={styles.state}>
            <EmptyState
              icon={BellOff}
              title={tab === 'unread' ? NOTIFICATIONS_UNREAD_EMPTY_LABEL : NOTIFICATIONS_EMPTY_LABEL}
            />
          </div>
        )}
        {items.map((notification) => (
          <NotificationRow key={notification.id} notification={notification} onOpen={onOpenIncident} />
        ))}
      </div>
    </div>
  )
}
