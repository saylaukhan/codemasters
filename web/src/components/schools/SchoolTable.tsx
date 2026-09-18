import { Table, type TableColumnType, type TableProps } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { SchoolListItem, SchoolSort } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import { formatDateTime, formatMs, formatSpeed, NO_VALUE } from '../../lib/format'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import { PAGE_SIZES } from './useSchoolListView'
import type { SchoolListView } from './queries'
import styles from './SchoolTable.module.css'

interface SchoolTableProps {
  items: SchoolListItem[]
  total: number
  view: SchoolListView
  loading: boolean
  empty: ReactNode
  onChange: (view: SchoolListView) => void
}

type Field = Exclude<SchoolSort, `-${string}`>

const orderOf = (sort: SchoolSort | undefined, field: Field): TableColumnType<SchoolListItem>['sortOrder'] =>
  sort === field ? 'ascend' : sort === `-${field}` ? 'descend' : null

/** Value under its threshold is highlighted (DESIGN.md §3.12). */
const metric = (value: string, below: boolean) => (
  <span className={below ? `${styles.number} ${styles.below}` : styles.number}>{value}</span>
)

/** School list of ТЗ п. 4: sorting and pages are on the server (T-24). */
export function SchoolTable({ items, total, view, loading, empty, onChange }: SchoolTableProps) {
  const column = (
    field: Field,
    title: string,
    render: (item: SchoolListItem) => ReactNode,
    numeric = false,
  ): TableColumnType<SchoolListItem> => ({
    key: field,
    title,
    sorter: true,
    sortOrder: orderOf(view.sort, field),
    align: numeric ? 'right' : undefined,
    render: (_: unknown, item: SchoolListItem) => render(item),
  })

  const columns: TableProps<SchoolListItem>['columns'] = [
    {
      ...column('full_name', 'Школа', (item) => <Link to={schoolCardPath(item.id)}>{item.fullName}</Link>),
      fixed: 'left',
      width: 280,
    },
    column('school_code', 'School ID', (item) => <span className={styles.code}>{item.schoolCode}</span>),
    column('region_name', 'Район', (item) => item.regionName),
    column('devices_count', 'ПК', (item) => <span className={styles.number}>{item.devicesCount}</span>, true),
    column(
      'avg_download_mbps',
      'Download',
      (item) =>
        metric(
          formatSpeed(item.avgDownloadMbps),
          item.avgDownloadMbps != null &&
            item.thresholds != null &&
            item.avgDownloadMbps < item.thresholds.downloadMinMbps,
        ),
      true,
    ),
    column(
      'avg_upload_mbps',
      'Upload',
      (item) =>
        metric(
          formatSpeed(item.avgUploadMbps),
          item.avgUploadMbps != null && item.thresholds != null && item.avgUploadMbps < item.thresholds.uploadMinMbps,
        ),
      true,
    ),
    column(
      'avg_ping_ms',
      'Ping',
      (item) =>
        metric(
          formatMs(item.avgPingMs),
          item.avgPingMs != null && item.thresholds != null && item.avgPingMs > item.thresholds.pingMaxMs,
        ),
      true,
    ),
    column('last_measured_at', 'Последний замер', (item) =>
      item.lastMeasuredAt ? formatDateTime(item.lastMeasuredAt) : NO_VALUE,
    ),
    column('status', 'Статус', (item) => <ConnectionStatusBadge status={item.status} />),
  ]

  return (
    <Table<SchoolListItem>
      rowKey="id"
      size="middle"
      columns={columns}
      dataSource={items}
      loading={loading}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: empty }}
      showSorterTooltip={false}
      pagination={{
        current: view.page,
        pageSize: view.pageSize,
        total,
        pageSizeOptions: PAGE_SIZES.map(String),
        showSizeChanger: true,
        showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
      }}
      onChange={(pagination, _filters, sorter) => {
        const active = Array.isArray(sorter) ? sorter[0] : sorter
        const field = active?.order ? (active.columnKey as Field) : undefined
        const sort = field ? ((active.order === 'descend' ? `-${field}` : field) as SchoolSort) : undefined
        const pageSize = pagination.pageSize ?? view.pageSize
        const sameOrder = sort === view.sort && pageSize === view.pageSize
        onChange({
          sort,
          pageSize,
          page: sameOrder ? (pagination.current ?? 1) : 1,
        })
      }}
    />
  )
}
