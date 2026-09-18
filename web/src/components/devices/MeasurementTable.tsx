import { Table, type TableProps } from 'antd'

import type { MeasurementListItem } from '../../api/types'
import { NO_VALUE, formatDateTime, formatMs, formatNumber, formatSpeed } from '../../lib/format'
import { IFACE_LABELS } from '../../lib/labels'
import styles from '../schools/SchoolCard.module.css'
import { ConnectionStatusBadge } from '../ui/StatusBadge'

type Metric = number | null | undefined

const metric = (text: string, alert: boolean) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)
const below = (value: Metric, min: Metric): boolean => value != null && min != null && value < min
const above = (value: Metric, max: Metric): boolean => value != null && max != null && value > max

const columns: TableProps<MeasurementListItem>['columns'] = [
  {
    key: 'measured',
    title: 'Дата и время',
    fixed: 'left',
    render: (_, m) => <span className={styles.number}>{formatDateTime(m.measuredAt)}</span>,
  },
  {
    key: 'download',
    title: 'Download',
    align: 'right',
    render: (_, m) => metric(formatSpeed(m.downloadMbps), below(m.downloadMbps, m.thresholdsSnapshot?.downloadMinMbps)),
  },
  {
    key: 'upload',
    title: 'Upload',
    align: 'right',
    render: (_, m) => metric(formatSpeed(m.uploadMbps), below(m.uploadMbps, m.thresholdsSnapshot?.uploadMinMbps)),
  },
  {
    key: 'ping',
    title: 'Ping',
    align: 'right',
    render: (_, m) => metric(formatMs(m.pingMs), above(m.pingMs, m.thresholdsSnapshot?.pingMaxMs)),
  },
  {
    key: 'jitter',
    title: 'Jitter',
    align: 'right',
    render: (_, m) => metric(formatMs(m.jitterMs), above(m.jitterMs, m.thresholdsSnapshot?.jitterMaxMs)),
  },
  {
    key: 'loss',
    title: 'Packet Loss',
    align: 'right',
    render: (_, m) =>
      metric(
        m.packetLossPct == null ? NO_VALUE : `${formatNumber(m.packetLossPct)} %`,
        above(m.packetLossPct, m.thresholdsSnapshot?.packetLossMaxPct),
      ),
  },
  {
    key: 'iface',
    title: 'Подключение',
    // Wi-Fi measurements do not rate the line (ADR-012): marked so they are not read as its quality.
    render: (_, m) =>
      m.ifaceType === 'wifi' ? (
        <div className={styles.stack}>
          <span>{IFACE_LABELS.wifi}</span>
          <span className={styles.muted}>Не оценивает линию</span>
        </div>
      ) : m.ifaceType ? (
        IFACE_LABELS[m.ifaceType]
      ) : (
        NO_VALUE
      ),
  },
  {
    key: 'status',
    title: 'Статус',
    render: (_, m) => (m.qualityStatus ? <ConnectionStatusBadge status={m.qualityStatus} /> : NO_VALUE),
  },
]

interface MeasurementTableProps {
  items: MeasurementListItem[]
  total: number
  page: number
  pageSize: number
  loading?: boolean
  onPageChange: (page: number, pageSize: number) => void
}

/** Measurement history of a computer (ТЗ п. 4), newest first, pages on the server. */
export function MeasurementTable({ items, total, page, pageSize, loading, onPageChange }: MeasurementTableProps) {
  return (
    <Table<MeasurementListItem>
      rowKey="measurementUuid"
      size="middle"
      columns={columns}
      dataSource={items}
      loading={loading}
      scroll={{ x: 'max-content' }}
      pagination={{ current: page, pageSize, total, showSizeChanger: true, onChange: onPageChange }}
    />
  )
}
