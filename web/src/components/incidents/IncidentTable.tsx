import { Table, type TableProps } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { IncidentListItem } from '../../api/types'
import { incidentCardPath, schoolCardPath } from '../../app/sections'
import { formatDateTime, NO_VALUE } from '../../lib/format'
import { LINE_STATUS_LABELS } from '../../lib/labels'
import { PAGE_SIZES } from '../schools/useSchoolListView'
import { IncidentStatusBadge } from '../ui/StatusBadge'
import styles from './Incident.module.css'
import { basisCaption, durationCaption } from './incidents'

type Column = NonNullable<TableProps<IncidentListItem>['columns']>[number]

const NUMBER: Column = {
  key: 'number',
  title: 'Номер',
  fixed: 'left',
  render: (_, item) => (
    <Link className={styles.code} to={incidentCardPath(item.id)}>
      {item.number}
    </Link>
  ),
}

const SCHOOL: Column = {
  key: 'school',
  title: 'Школа',
  render: (_, item) => (
    <span className={styles.stack}>
      <Link to={schoolCardPath(item.schoolId)}>{item.schoolName}</Link>
      <span className={`${styles.code} ${styles.muted}`}>{item.schoolCode}</span>
    </span>
  ),
}

const REST: Column[] = [
  { key: 'status', title: 'Статус', render: (_, item) => <IncidentStatusBadge status={item.status} /> },
  {
    key: 'line',
    title: 'Линия и поставщик',
    render: (_, item) => (
      <span className={styles.stack}>
        <span>{LINE_STATUS_LABELS[item.lineStatus]}</span>
        <span className={styles.muted}>{item.providerName}</span>
      </span>
    ),
  },
  { key: 'basis', title: 'Основания', render: (_, item) => basisCaption(item.basisMetrics) },
  {
    key: 'started',
    title: 'Начало',
    render: (_, item) => <span className={styles.number}>{formatDateTime(item.startedAt)}</span>,
  },
  {
    key: 'duration',
    title: 'Длительность',
    align: 'right',
    render: (_, item) => (
      <span className={item.durationS === null ? `${styles.number} ${styles.muted}` : styles.number}>
        {durationCaption(item)}
      </span>
    ),
  },
  { key: 'responsible', title: 'Ответственный', render: (_, item) => item.responsibleUserName ?? NO_VALUE },
]

interface IncidentTableProps {
  items: IncidentListItem[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  empty: ReactNode
  onPageChange: (page: number, pageSize: number) => void
  /** The school card leaves its own school out. */
  showSchool?: boolean
}

/** Incidents of ТЗ п. 19, newest first; pages are on the server (T-41). */
export function IncidentTable({
  items,
  total,
  page,
  pageSize,
  loading,
  empty,
  onPageChange,
  showSchool = true,
}: IncidentTableProps) {
  return (
    <Table<IncidentListItem>
      rowKey="id"
      size="middle"
      columns={showSchool ? [NUMBER, SCHOOL, ...REST] : [NUMBER, ...REST]}
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
