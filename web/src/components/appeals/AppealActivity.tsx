import { Timeline } from 'antd'

import type { AppealEventDetail } from '../../api/types'
import { formatDateTime, NO_VALUE } from '../../lib/format'
import styles from './Appeal.module.css'
import { appealEventCaption } from './appeals'

/**
 * History of an appeal (ТЗ п. 17, DESIGN.md §3.17): dots of 8px, the author, the time, the action. The first entry
 * is the sending; every status change and every comment is an entry of `appeal_events`. The form that adds them is
 * next to the feed, for a role with `appeals:update`.
 */
export function AppealActivity({ events }: { events: AppealEventDetail[] }) {
  return (
    <Timeline
      items={events.map((event) => ({
        key: event.id,
        dot: <span className={styles.dot} aria-hidden />,
        children: (
          <>
            <div className={styles.eventHead}>
              <span className={styles.author}>{event.authorUserName || NO_VALUE}</span>
              <span className={styles.time}>{formatDateTime(event.createdAt)}</span>
            </div>
            <p className={styles.eventText}>{appealEventCaption(event)}</p>
            {event.comment && <p className={styles.comment}>{event.comment}</p>}
          </>
        ),
      }))}
    />
  )
}
