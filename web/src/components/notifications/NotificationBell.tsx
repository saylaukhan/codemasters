import { Dropdown } from 'antd'
import { Bell } from 'lucide-react'
import { useState } from 'react'

import { NOTIFICATIONS_TITLE } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { NotificationPanel } from './NotificationPanel'
import styles from './Notifications.module.css'
import { unreadCaption } from './notifications'
import { useNotificationStream, useUnreadCount } from './queries'

/**
 * Bell of the header with its counter (DESIGN.md §3.5); the panel of §3.23 drops out of it.
 * The stream is listened to while the panel is signed in, so a new notification arrives whatever
 * page is open and whether or not the bell is unfolded (T-42).
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const unread = useUnreadCount().data?.unread ?? 0
  useNotificationStream(true)

  return (
    <Dropdown
      open={open}
      onOpenChange={setOpen}
      trigger={['click']}
      placement="bottomRight"
      popupRender={() => <NotificationPanel onOpenIncident={() => setOpen(false)} />}
    >
      <span className={styles.bell}>
        <Button
          kind="flat"
          tooltip={NOTIFICATIONS_TITLE}
          icon={<Bell size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} />}
        />
        {unread > 0 && <span className={styles.counter}>{unreadCaption(unread)}</span>}
      </span>
    </Dropdown>
  )
}
