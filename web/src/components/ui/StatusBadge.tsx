import type { IncidentStatus, SchoolStatus } from '../../api/types'
import { INCIDENT_STATUS_LABELS, SCHOOL_STATUS_LABELS } from '../../lib/labels'
import styles from './StatusBadge.module.css'

/** Connection status of a school, line or measurement: dot + caption (DESIGN.md §3.11, §4.1). */
export function ConnectionStatusBadge({ status }: { status: SchoolStatus }) {
  return (
    <span className={styles.badge} data-status={status}>
      <span className={styles.dot} aria-hidden />
      {SCHOOL_STATUS_LABELS[status]}
    </span>
  )
}

/** Status of an incident or an appeal: caption without a dot (DESIGN.md §3.11, §4.2). */
export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span className={styles.badge} data-status={status}>
      {INCIDENT_STATUS_LABELS[status]}
    </span>
  )
}
