import { Table, type TableColumnType } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { AnalyticsLevel } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import { formatMs, formatNumber, formatPercent, formatSpeed, NO_VALUE } from '../../lib/format'
import styles from './Analytics.module.css'
import type { RankedRow } from './report'

type Metric = 'downloadMbps' | 'uploadMbps' | 'pingMs'

const NAME_TITLES: Record<AnalyticsLevel, string> = {
  school: 'Школа',
  district: 'Район/город',
  provider: 'Провайдер',
  region: 'Область',
}

/** Ascending order with empty values last in both directions of the column. */
const byValue =
  (value: (row: RankedRow) => number | null | undefined) =>
  (a: RankedRow, b: RankedRow, order?: 'ascend' | 'descend' | null) => {
    const [x, y] = [value(a), value(b)]
    if (x == null || y == null) return x == null && y == null ? 0 : (x == null ? 1 : -1) * (order === 'descend' ? -1 : 1)
    return x - y
  }

const number = (text: string, alert = false) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)

interface RatingTableProps {
  level: AnalyticsLevel
  rows: RankedRow[]
  availabilityMinPct: number
  loading: boolean
  empty: ReactNode
}

/** Rating of schools, districts or providers for the period: avg / min / max, count, availability (ТЗ п. 5). */
export function RatingTable({ level, rows, availabilityMinPct, loading, empty }: RatingTableProps) {
  const metric = (key: Metric, title: string, format: (value: number) => string): TableColumnType<RankedRow> => ({
    key,
    title,
    align: 'right',
    sorter: byValue((row) => row[key]?.avg),
    render: (_, row) => {
      const stats = row[key]
      if (!stats) return NO_VALUE
      return (
        <span className={`${styles.number} ${styles.stats}`}>
          {format(stats.avg)}
          <span className={styles.range}>
            {format(stats.min)} – {format(stats.max)}
          </span>
        </span>
      )
    },
  })

  const columns: TableColumnType<RankedRow>[] = [
    {
      key: 'rank',
      title: 'Место',
      width: 72,
      align: 'right',
      defaultSortOrder: 'ascend',
      sorter: byValue((row) => row.rank),
      render: (_, row) => number(row.rank === null ? NO_VALUE : String(row.rank)),
    },
    {
      key: 'name',
      title: NAME_TITLES[level],
      width: 280,
      sorter: (a, b) => (a.name ?? '').localeCompare(b.name ?? '', 'ru'),
      render: (_, row) =>
        level === 'school' && row.id !== null ? (
          <Link to={schoolCardPath(row.id)}>{row.name}</Link>
        ) : (
          (row.name ?? 'Вся ВКО')
        ),
    },
    {
      key: 'measurements',
      title: 'Замеров',
      align: 'right',
      sorter: byValue((row) => row.measurementsCount),
      render: (_, row) => number(formatNumber(row.measurementsCount, 0)),
    },
    {
      key: 'problems',
      title: 'Проблемных',
      align: 'right',
      sorter: byValue((row) => row.problemPct),
      render: (_, row) => number(formatPercent(row.problemPct)),
    },
    metric('downloadMbps', 'Download', formatSpeed),
    metric('uploadMbps', 'Upload', formatSpeed),
    metric('pingMs', 'Ping', formatMs),
    {
      key: 'availability',
      title: 'Доступность',
      align: 'right',
      sorter: byValue((row) => row.availabilityPct),
      render: (_, row) =>
        number(
          formatPercent(row.availabilityPct, 2),
          row.availabilityPct !== null && row.availabilityPct < availabilityMinPct,
        ),
    },
    {
      key: 'contract',
      title: 'Ниже договора',
      align: 'right',
      sorter: byValue((row) => row.belowContractPct),
      render: (_, row) => number(formatPercent(row.belowContractPct)),
    },
  ]

  return (
    <Table<RankedRow>
      rowKey={(row) => row.id ?? 0}
      size="middle"
      columns={level === 'region' ? columns.slice(1) : columns}
      dataSource={rows}
      loading={loading}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: empty }}
      showSorterTooltip={false}
      pagination={
        rows.length > 25 && {
          defaultPageSize: 25,
          pageSizeOptions: ['25', '50', '100'],
          showSizeChanger: true,
          showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
        }
      }
    />
  )
}
