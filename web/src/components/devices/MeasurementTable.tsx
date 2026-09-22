import type { MeasurementListItem } from '../../api/types'
import { NO_VALUE, formatDateTime, formatMs, formatNumber, formatSpeed } from '../../lib/format'
import { IFACE_LABELS, IFACE_NOTE_LABELS } from '../../lib/labels'
import styles from '../schools/SchoolCard.module.css'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import { ConnectionStatusBadge } from '../ui/StatusBadge'

type Metric = number | null | undefined

const metric = (text: string, alert: boolean) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)
const below = (value: Metric, min: Metric): boolean => value != null && min != null && value < min
const above = (value: Metric, max: Metric): boolean => value != null && max != null && value > max

// The history of measurements is the case of DESIGN.md §3.12 where columns cannot be merged: at
// 769–1024 it pages sideways with the time pinned, at ≤ 768 every measurement becomes a card.
/** Wi-Fi measurements do not rate the line (ADR-012): the note travels with the interface. */
const ifaceCaption = (m: MeasurementListItem): string => {
  if (!m.ifaceType) return NO_VALUE
  const note = m.ifaceType === 'wifi' ? ` · ${IFACE_NOTE_LABELS.wifi}` : ''
  return `${IFACE_LABELS[m.ifaceType]}${note}`
}

const columns: readonly ResponsiveColumn<MeasurementListItem>[] = [
  {
    key: 'measured',
    title: 'Дата и время',
    priority: 'primary',
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
    priority: 'minor',
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
    priority: 'primary',
    render: (_, m) =>
      m.ifaceType === 'wifi' ? (
        <div className={styles.stack}>
          <span>{IFACE_LABELS.wifi}</span>
          <span className={styles.muted}>{IFACE_NOTE_LABELS.wifi}</span>
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
    priority: 'primary',
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
    <ResponsiveTable<MeasurementListItem>
      rowKey="measurementUuid"
      size="middle"
      columns={columns}
      dataSource={items}
      loading={loading}
      scroll={{ x: 'max-content' }}
      card={{
        title: (m) => formatDateTime(m.measuredAt),
        status: (m) => (m.qualityStatus ? <ConnectionStatusBadge status={m.qualityStatus} /> : NO_VALUE),
        description: (m) => ifaceCaption(m),
      }}
      pagination={{ current: page, pageSize, total, showSizeChanger: true, onChange: onPageChange }}
    />
  )
}
