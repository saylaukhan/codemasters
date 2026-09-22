import { Link } from 'react-router'

import type { DeviceListItem } from '../../api/types'
import { deviceCardPath } from '../../app/sections'
import { NO_VALUE, formatDateTime, formatMs, formatRelative, formatSpeed } from '../../lib/format'
import { DEVICE_STATUS_LABELS, IFACE_LABELS, LINE_STATUS_LABELS } from '../../lib/labels'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './SchoolCard.module.css'

type Metric = number | null | undefined

const metric = (text: string, alert: boolean) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)
const below = (value: Metric, min: Metric): boolean => value != null && min != null && value < min
const above = (value: Metric, max: Metric): boolean => value != null && max != null && value > max

// The widest table of the panel (DESIGN.md §3.12): the place and the line read from the card
// description on a phone, the last contact and the agent version go first when the width runs out.
const status = (item: DeviceListItem) =>
  item.status === 'blocked' ? (
    <span className={styles.muted}>{DEVICE_STATUS_LABELS.blocked}</span>
  ) : (
    <ConnectionStatusBadge status={item.currentStatus} />
  )

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
  { key: 'status', title: 'Статус', priority: 'primary', render: (_, item) => status(item) },
]

/** Computers of the school (ТЗ п. 4): place, last measurement, last contact and status. */
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
        status,
        description: (item) =>
          [item.room, item.monitoringPointName, LINE_STATUS_LABELS[item.lineStatus]].filter(Boolean).join(' · '),
      }}
      pagination={items.length > 20 ? { pageSize: 20, showSizeChanger: false } : false}
    />
  )
}
