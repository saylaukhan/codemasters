import { Link } from 'react-router'

import type { DeviceListItem } from '../../api/types'
import { deviceCardPath } from '../../app/sections'
import { NO_VALUE, formatDateTime, formatMs, formatRelative, formatSpeed } from '../../lib/format'
import { IFACE_LABELS, LINE_STATUS_LABELS, NO_DATA_BLOCKED_HINT, NO_DATA_HINT } from '../../lib/labels'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './SchoolCard.module.css'

type Metric = number | null | undefined

const metric = (text: string, alert: boolean) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)
const below = (value: Metric, min: Metric): boolean => value != null && min != null && value < min
const above = (value: Metric, max: Metric): boolean => value != null && max != null && value > max

/**
 * The column says the quality of the connection, not whether the computer is allowed to send:
 * blocking lives in the administration («Активно» / «Заблокировано»), here it is only the reason
 * there is nothing to judge by. «Нет данных» never stands without that reason (DESIGN.md §4.1).
 */
const noDataHint = (item: DeviceListItem): string | null => {
  if (item.currentStatus !== 'no_data') return null
  return item.status === 'blocked' ? NO_DATA_BLOCKED_HINT : NO_DATA_HINT
}

const quality = (item: DeviceListItem) => {
  const hint = noDataHint(item)
  return (
    <div className={styles.stack}>
      <ConnectionStatusBadge status={item.currentStatus} />
      {hint && <span className={styles.hint}>{hint}</span>}
    </div>
  )
}

// The widest table of the panel (DESIGN.md §3.12): the place and the line read from the card
// description on a phone, the last contact and the agent version go first when the width runs out.
const columns: readonly ResponsiveColumn<DeviceListItem>[] = [
  {
    key: 'device',
    title: 'Компьютер',
    priority: 'primary',
    fixed: 'left',
    render: (_, item) => (
      <div className={styles.stack}>
        <Link to={deviceCardPath(item.id)}>{item.hostname ?? item.deviceUid}</Link>
        <span className={styles.code}>{item.deviceUid}</span>
      </div>
    ),
  },
  {
    key: 'room',
    title: 'Кабинет',
    priority: 'primary',
    render: (_, item) => (
      <div className={styles.stack}>
        <span>{item.room ?? NO_VALUE}</span>
        <span className={styles.muted}>{item.monitoringPointName}</span>
      </div>
    ),
  },
  { key: 'line', title: 'Линия', priority: 'primary', render: (_, item) => LINE_STATUS_LABELS[item.lineStatus] },
  {
    key: 'download',
    title: 'Download',
    align: 'right',
    render: (_, { latestMeasurement: m }) =>
      metric(formatSpeed(m?.downloadMbps), below(m?.downloadMbps, m?.thresholdsSnapshot?.downloadMinMbps)),
  },
  {
    key: 'upload',
    title: 'Upload',
    align: 'right',
    render: (_, { latestMeasurement: m }) =>
      metric(formatSpeed(m?.uploadMbps), below(m?.uploadMbps, m?.thresholdsSnapshot?.uploadMinMbps)),
  },
  {
    key: 'ping',
    title: 'Ping',
    align: 'right',
    render: (_, { latestMeasurement: m }) =>
      metric(formatMs(m?.pingMs), above(m?.pingMs, m?.thresholdsSnapshot?.pingMaxMs)),
  },
  {
    key: 'measured',
    title: 'Последний замер',
    render: (_, { latestMeasurement: m }) =>
      m ? (
        <div className={styles.stack}>
          <span>{formatDateTime(m.measuredAt)}</span>
          {m.ifaceType && <span className={styles.muted}>{IFACE_LABELS[m.ifaceType]}</span>}
        </div>
      ) : (
        NO_VALUE
      ),
  },
  { key: 'seen', title: 'Последняя связь', priority: 'minor', render: (_, item) => formatRelative(item.lastSeenAt) },
  { key: 'version', title: 'Версия агента', priority: 'minor', render: (_, item) => item.agentVersion ?? NO_VALUE },
  { key: 'quality', title: 'Качество', priority: 'primary', render: (_, item) => quality(item) },
]

/** Computers of the school (ТЗ п. 4): place, last measurement, last contact and quality. */
export function DeviceTable({ items }: { items: DeviceListItem[] }) {
  return (
    <ResponsiveTable<DeviceListItem>
      rowKey="id"
      size="middle"
      columns={columns}
      dataSource={items}
      scroll={{ x: 'max-content' }}
      card={{
        title: (item) => <Link to={deviceCardPath(item.id)}>{item.hostname ?? item.deviceUid}</Link>,
        // The head of a card holds a pill, so on a phone the reason for «Нет данных» goes to the
        // line under the title instead of a second line next to the pill.
        status: (item) => <ConnectionStatusBadge status={item.currentStatus} />,
        description: (item) =>
          [item.room, item.monitoringPointName, LINE_STATUS_LABELS[item.lineStatus], noDataHint(item)]
            .filter(Boolean)
            .join(' · '),
      }}
      pagination={items.length > 20 ? { pageSize: 20, showSizeChanger: false } : false}
    />
  )
}
