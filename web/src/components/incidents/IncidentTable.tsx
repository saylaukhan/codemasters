import { Table, type TableProps } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { IncidentListItem } from '../../api/types'
import { incidentCardPath, schoolCardPath } from '../../app/sections'
import { formatDateTime, NO_VALUE } from '../../lib/format'
import { INCIDENT_COLUMN_LABELS, LINE_STATUS_LABELS, TABLE_PAGINATION_LABELS } from '../../lib/labels'
import { PAGE_SIZES } from '../schools/useSchoolListView'
import { IncidentStatusBadge } from '../ui/StatusBadge'
import styles from './Incident.module.css'
import { basisCaption, durationCaption } from './incidents'

type Column = NonNullable<TableProps<IncidentListItem>['columns']>[number]

const NUMBER: Column = {
  key: 'number',
  title: INCIDENT_COLUMN_LABELS.number,
  fixed: 'left',
  render: (_, item) => (
    <Link className={styles.code} to={incidentCardPath(item.id)}>
      {item.number}
    </Link>
  ),
}

const SCHOOL: Column = {
  key: 'school',
  title: INCIDENT_COLUMN_LABELS.school,
  render: (_, item) => (
    <span className={styles.stack}>
      <Link to={schoolCardPath(item.schoolId)}>{item.schoolName}</Link>
      <span className={`${styles.code} ${styles.muted}`}>{item.schoolCode}</span>
    </span>
  ),
}

const REST: Column[] = [
  { key: 'status', title: INCIDENT_COLUMN_LABELS.status, render: (_, item) => <IncidentStatusBadge status={item.status} /> },
  {
    key: 'line',
    title: INCIDENT_COLUMN_LABELS.line,
    render: (_, item) => (
      <span className={styles.stack}>
        <span>{LINE_STATUS_LABELS[item.lineStatus]}</span>
        <span className={styles.muted}>{item.providerName}</span>
      </span>
    ),
  },
  { key: 'basis', title: INCIDENT_COLUMN_LABELS.basis, render: (_, item) => basisCaption(item.basisMetrics) },
  {
    key: 'started',
    title: INCIDENT_COLUMN_LABELS.startedAt,
    render: (_, item) => <span className={styles.number}>{formatDateTime(item.startedAt)}</span>,
  },
  {
    key: 'duration',
    title: INCIDENT_COLUMN_LABELS.duration,
    align: 'right',
    render: (_, item) => (
      <span className={item.durationS === null ? `${styles.number} ${styles.muted}` : styles.number}>
        {durationCaption(item)}
      </span>
    ),
  },
  { key: 'responsible', title: INCIDENT_COLUMN_LABELS.responsible, render: (_, item) => item.responsibleUserName ?? NO_VALUE },
]

interface IncidentTableProps {
  items: IncidentListItem[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  empty: ReactNode
  /** Required while the footer is there: a cut list of five rows turns it off instead (T-60). */
  onPageChange?: (page: number, pageSize: number) => void
  /** The school card leaves its own school out. */
  showSchool?: boolean
  /** The main screen shows the five newest incidents and pages them nowhere (DESIGN.md §3.28). */
  pagination?: boolean
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
  pagination = true,
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
      pagination={
        pagination && {
          current: page,
          pageSize,
          total,
          pageSizeOptions: PAGE_SIZES.map(String),
          showSizeChanger: true,
          showTotal: (count, [from, to]) => TABLE_PAGINATION_LABELS.total(from, to, count),
        }
      }
      onChange={(next) => {
        const size = next.pageSize ?? pageSize
        onPageChange?.(size === pageSize ? (next.current ?? 1) : 1, size)
      }}
    />
  )
}
