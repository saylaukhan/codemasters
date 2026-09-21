import type { DeviceStatus, ExportStatus, IncidentStatus, SchoolStatus } from '../../api/types'
import {
  DEVICE_STATUS_LABELS,
  EXPORT_STATUS_LABELS,
  INCIDENT_STATUS_LABELS,
  SCHOOL_ACTIVITY_LABELS,
  SCHOOL_STATUS_LABELS,
  USER_STATUS_LABELS,
  type SchoolActivity,
} from '../../lib/labels'
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

interface IncidentStatusBadgeProps {
  status: IncidentStatus
  /**
   * Dictionary to read the caption from. The school cabinet says the same six statuses in its own
   * words — «У поставщика», «Ждём ответа» (DESIGN.md §4.2) — so the caller passes that dictionary
   * instead of a string of its own (ADR-013).
   */
  labels?: Record<IncidentStatus, string>
}

/** Status of an incident or an appeal: caption without a dot (DESIGN.md §3.11, §4.2). */
export function IncidentStatusBadge({ status, labels = INCIDENT_STATUS_LABELS }: IncidentStatusBadgeProps) {
  return (
    <span className={styles.badge} data-status={status}>
      {labels[status]}
    </span>
  )
}

/** State of an export's file (T-33): caption without a dot, colours of «in progress», «Норма», «Критично». */
export function ExportStatusBadge({ status }: { status: ExportStatus }) {
  return (
    <span className={styles.badge} data-export={status}>
      {EXPORT_STATUS_LABELS[status]}
    </span>
  )
}

/** Activity of a school in the administration (T-34): a disabled one keeps its history, shown grey. */
export function SchoolActivityBadge({ active }: { active: boolean }) {
  const activity: SchoolActivity = active ? 'active' : 'disabled'
  return (
    <span className={styles.badge} data-activity={activity}>
      {SCHOOL_ACTIVITY_LABELS[activity]}
    </span>
  )
}

/** Status of a device in the administration (T-36): colours of an active or a disabled school, blocked is grey. */
export function DeviceStatusBadge({ status }: { status: DeviceStatus }) {
  return (
    <span className={styles.badge} data-activity={status === 'active' ? 'active' : 'disabled'}>
      {DEVICE_STATUS_LABELS[status]}
    </span>
  )
}

/** Status of a panel user (T-38): colours of an active or a disabled school, blocked is grey. */
export function UserStatusBadge({ active }: { active: boolean }) {
  return (
    <span className={styles.badge} data-activity={active ? 'active' : 'disabled'}>
      {USER_STATUS_LABELS[active ? 'active' : 'blocked']}
    </span>
  )
}
