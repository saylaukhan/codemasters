import { Table, type TableProps } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { AppealListItem } from '../../api/types'
import { appealCardPath, schoolCardPath } from '../../app/sections'
import { formatDateTime } from '../../lib/format'
import { APPEAL_COLUMN_LABELS, APPEAL_DELIVERY_LABELS, APPEAL_NOT_SENT_HINT } from '../../lib/labels'
import { PAGE_SIZES } from '../schools/useSchoolListView'
import { IncidentStatusBadge } from '../ui/StatusBadge'
import styles from './Appeal.module.css'

const COLUMNS: NonNullable<TableProps<AppealListItem>['columns']> = [
  {
    key: 'number',
    title: APPEAL_COLUMN_LABELS.number,
    fixed: 'left',
    render: (_, item) => (
      <Link className={styles.code} to={appealCardPath(item.id)}>
        {item.number}
      </Link>
    ),
  },
  {
    key: 'status',
    title: APPEAL_COLUMN_LABELS.status,
    render: (_, item) => <IncidentStatusBadge status={item.status} />,
  },
  {
    key: 'school',
    title: APPEAL_COLUMN_LABELS.school,
    render: (_, item) => (
      <span className={styles.stack}>
        <Link to={schoolCardPath(item.schoolId)}>{item.schoolName}</Link>
        <span className={`${styles.code} ${styles.muted}`}>{item.schoolCode}</span>
      </span>
    ),
  },
  { key: 'provider', title: APPEAL_COLUMN_LABELS.provider, render: (_, item) => item.providerName },
  { key: 'subject', title: APPEAL_COLUMN_LABELS.subject, render: (_, item) => item.subject },
  {
    key: 'sent',
    title: APPEAL_COLUMN_LABELS.sentAt,
    render: (_, item) => <span className={styles.number}>{formatDateTime(item.sentAt)}</span>,
  },
  {
    key: 'delivery',
    title: APPEAL_COLUMN_LABELS.delivery,
    render: (_, item) => (
      // The appeal and its PDF are kept even when the letter did not go (ADR-011), so this is a caption, not an error.
      <span
        className={item.deliveryStatus === 'sent' ? undefined : styles.muted}
        title={item.deliveryStatus === 'sent' ? undefined : APPEAL_NOT_SENT_HINT}
      >
        {APPEAL_DELIVERY_LABELS[item.deliveryStatus]}
      </span>
    ),
  },
]

interface AppealTableProps {
  items: AppealListItem[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  empty: ReactNode
  onPageChange: (page: number, pageSize: number) => void
}

/** Sent appeals of ТЗ п. 17, newest first; pages are on the server (T-48). */
export function AppealTable({ items, total, page, pageSize, loading, empty, onPageChange }: AppealTableProps) {
  return (
    <Table<AppealListItem>
      rowKey="id"
      size="middle"
      columns={COLUMNS}
      dataSource={items}
      loading={loading}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: empty }}
      pagination={{
        current: page,
        pageSize,
        total,
        pageSizeOptions: PAGE_SIZES.map(String),
        showSizeChanger: true,
        showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
      }}
      onChange={(pagination) => {
        const size = pagination.pageSize ?? pageSize
        onPageChange(size === pageSize ? (pagination.current ?? 1) : 1, size)
      }}
    />
  )
}
